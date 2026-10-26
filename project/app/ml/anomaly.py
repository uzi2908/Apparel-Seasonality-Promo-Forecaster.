"""Live panic-buy detector (IsolationForest) over quantity + volume velocity.

There is no transaction-level history yet, so the model is trained on synthetic
"normal" traffic generated from the hard-coded baselines in `app.constants`.
Swap `generate_normal_traffic` for a real query once such history exists.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from app.constants import TRANSACTION_BASELINES, get_baseline

NORMAL = "NORMAL"
ELEVATED = "ELEVATED"
CRITICAL = "CRITICAL_PANIC_BUY"

# decision_function() < 0 => outside the bulk of normal traffic (ELEVATED);
# below CRITICAL_SCORE => clearly extreme (CRITICAL). IsolationForest scores
# saturate around -0.07 on this feature space, hence the small magnitude.
CRITICAL_SCORE = -0.055


@dataclass(frozen=True)
class AnomalyVerdict:
    risk_level: str
    score: float

    @property
    def is_anomaly(self) -> bool:
        return self.risk_level != NORMAL

    @property
    def manager_action_required(self) -> bool:
        return self.risk_level == CRITICAL


def make_features(
    category: str, quantity: float, velocity_units: float, velocity_txns: float
) -> list[float]:
    """Scale-free features so one model serves every product."""
    b = get_baseline(category)
    return [
        (quantity - b.mean_quantity) / b.std_quantity,
        quantity / b.mean_quantity,
        velocity_units / b.mean_quantity,
        velocity_txns,
    ]


def _sample_quantities(
    rng: np.random.Generator, category: str, size: int
) -> np.ndarray:
    b = get_baseline(category)
    return np.clip(np.rint(rng.normal(b.mean_quantity, b.std_quantity, size)), 1, None)


def generate_normal_traffic(
    rng: np.random.Generator, per_category: int = 5000
) -> np.ndarray:
    rows: list[list[float]] = []
    for category in TRANSACTION_BASELINES:
        qty = _sample_quantities(rng, category, per_category)
        # Other transactions for the same store+product inside the velocity window.
        extra_txns = rng.poisson(1.5, per_category)
        for q, n_extra in zip(qty, extra_txns):
            others = (
                _sample_quantities(rng, category, int(n_extra)).sum()
                if n_extra
                else 0.0
            )
            rows.append(make_features(category, q, q + others, 1 + n_extra))
    return np.array(rows)


class AnomalyModel:
    def __init__(self, forest: IsolationForest, trained_at: str):
        self.forest = forest
        self.trained_at = trained_at

    @classmethod
    def train(cls, random_state: int = 42) -> "AnomalyModel":
        rng = np.random.default_rng(random_state)
        X = generate_normal_traffic(rng)
        forest = IsolationForest(
            n_estimators=200, contamination=0.005, random_state=random_state
        ).fit(X)
        return cls(forest, datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"forest": self.forest, "trained_at": self.trained_at}, path)

    @classmethod
    def load(cls, path: Path) -> "AnomalyModel":
        blob = joblib.load(path)
        return cls(blob["forest"], blob["trained_at"])

    def assess(
        self, category: str, quantity: int, velocity_units: int, velocity_txns: int
    ) -> AnomalyVerdict:
        """`velocity_*` must already include the transaction being assessed."""
        features = np.array(
            [make_features(category, quantity, velocity_units, velocity_txns)]
        )
        score = float(self.forest.decision_function(features)[0])

        # Hard guard: one basket, or the units drained from one store inside the
        # velocity window, reaching the product's critical quantity is always critical
        # (the forest alone can't rank how far outside its training range a point is).
        critical_qty = get_baseline(category).critical_quantity
        if (
            quantity >= critical_qty
            or velocity_units >= critical_qty
            or score < CRITICAL_SCORE
        ):
            level = CRITICAL
        elif score < 0:
            level = ELEVATED
        else:
            level = NORMAL
        return AnomalyVerdict(risk_level=level, score=round(score, 4))
