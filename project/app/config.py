"""Runtime configuration. Everything can be overridden with environment variables."""

import os
from pathlib import Path

APP_VERSION = "1.0.0"

PROJECT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_DIR.parent

# Default DB is the SQLite file that lives at the repo root (table: daily_sales).
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{REPO_ROOT / 'retail_sales.db'}")

# Trained model artefacts (git-ignored via project/.gitignore -> models/).
MODEL_DIR = Path(os.getenv("MODEL_DIR", PROJECT_DIR / "models"))
FORECAST_MODEL_PATH = MODEL_DIR / "forecast_model.joblib"
ANOMALY_MODEL_PATH = MODEL_DIR / "anomaly_model.joblib"

# Sliding window used to measure "volume velocity" per store + product.
VELOCITY_WINDOW_SECONDS = int(os.getenv("VELOCITY_WINDOW_SECONDS", "60"))
