"""Promo-impact regression model (RandomForest) trained on the `daily_sales` table."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.ml.features import build_features, is_festival_date

# Prediction interval = spread of the individual trees (10th - 90th percentile).
INTERVAL_LOW_PCT = 10
INTERVAL_HIGH_PCT = 90


class UnknownCategoryError(ValueError):
    pass


@dataclass(frozen=True)
class ForecastResult:
    units: int
    lower: float
    upper: float


class ForecastModel:
    def __init__(
        self, pipeline: Pipeline, categories: list[str], metrics: dict, trained_at: str
    ):
        self.pipeline = pipeline
        self.categories = categories
        self.metrics = metrics
        self.trained_at = trained_at

    # ---- training -------------------------------------------------------
    @classmethod
    def train(cls, engine: Engine, random_state: int = 42) -> "ForecastModel":
        df = pd.read_sql(
            text(
                "SELECT Date, Category, Base_Price, Discount_Applied, Units_Sold "
                "FROM daily_sales"
            ),
            engine,
        )
        if df.empty:
            raise RuntimeError("daily_sales is empty; cannot train the forecast model")

        dates = pd.to_datetime(df["Date"])
        X = build_features(
            df["Category"],
            df["Base_Price"],
            df["Discount_Applied"],
            [is_festival_date(d.date()) for d in dates],
            dates.dt.month,
        )
        y = df["Units_Sold"].astype(float)

        def new_pipeline() -> Pipeline:
            pre = ColumnTransformer(
                [
                    (
                        "cat",
                        OneHotEncoder(handle_unknown="error", sparse_output=False),
                        ["category"],
                    )
                ],
                remainder="passthrough",
                sparse_threshold=0,
            )
            rf = RandomForestRegressor(
                n_estimators=200,
                min_samples_leaf=5,
                n_jobs=-1,
                random_state=random_state,
            )
            return Pipeline([("pre", pre), ("rf", rf)])

        # Hold-out score for reporting only; the shipped model is refit on everything.
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.2, random_state=random_state
        )
        probe = new_pipeline().fit(X_tr, y_tr)
        pred = probe.predict(X_te)
        metrics = {
            "mae": round(float(mean_absolute_error(y_te, pred)), 3),
            "r2": round(float(r2_score(y_te, pred)), 3),
            "rows": int(len(df)),
        }

        pipeline = new_pipeline().fit(X, y)
        return cls(
            pipeline,
            sorted(df["Category"].unique().tolist()),
            metrics,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    # ---- persistence ----------------------------------------------------
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "categories": self.categories,
                "metrics": self.metrics,
                "trained_at": self.trained_at,
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> "ForecastModel":
        blob = joblib.load(path)
        return cls(
            blob["pipeline"], blob["categories"], blob["metrics"], blob["trained_at"]
        )

    # ---- inference ------------------------------------------------------
    def predict(
        self,
        category: str,
        base_price: float,
        discount_pct: float,
        is_festival: bool,
        on_date: date,
    ) -> ForecastResult:
        if category not in self.categories:
            raise UnknownCategoryError(
                f"Unknown category '{category}'. Valid categories: {self.categories}"
            )

        X = build_features(
            [category], [base_price], [discount_pct], [is_festival], [on_date.month]
        )
        Xt = self.pipeline.named_steps["pre"].transform(X)
        forest = self.pipeline.named_steps["rf"]

        per_tree = np.array([tree.predict(Xt)[0] for tree in forest.estimators_])
        mean = float(per_tree.mean())
        lower = float(np.percentile(per_tree, INTERVAL_LOW_PCT))
        upper = float(np.percentile(per_tree, INTERVAL_HIGH_PCT))
        return ForecastResult(
            units=max(0, round(mean)),
            lower=round(max(0.0, min(lower, mean)), 2),
            upper=round(max(upper, mean), 2),
        )
