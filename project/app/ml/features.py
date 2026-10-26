"""Feature engineering shared by training and inference (keeps them from drifting apart)."""

from datetime import date

import numpy as np
import pandas as pd

from app.constants import FESTIVAL_WINDOWS

FEATURE_COLUMNS = [
    "category",
    "base_price",
    "discount_pct",
    "is_festival",
    "month_sin",
    "month_cos",
]


def is_festival_date(d: date) -> bool:
    return any(start <= d <= end for start, end in FESTIVAL_WINDOWS)


def build_features(
    category: pd.Series | list[str],
    base_price: pd.Series | list[float],
    discount_pct: pd.Series | list[float],
    is_festival: pd.Series | list[bool],
    month: pd.Series | list[int],
) -> pd.DataFrame:
    """Turn raw inputs into the model's feature frame. Month is encoded cyclically."""
    month_arr = np.asarray(month, dtype=float)
    return pd.DataFrame(
        {
            "category": list(category),
            "base_price": np.asarray(base_price, dtype=float),
            "discount_pct": np.asarray(discount_pct, dtype=float),
            "is_festival": np.asarray(is_festival, dtype=int),
            "month_sin": np.sin(2 * np.pi * month_arr / 12),
            "month_cos": np.cos(2 * np.pi * month_arr / 12),
        }
    )[FEATURE_COLUMNS]
