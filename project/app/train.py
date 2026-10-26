"""Retrain both models and save them:  uv run python -m app.train"""

from app.database import engine
from app.ml.registry import load_models


def main() -> None:
    registry = load_models(engine, retrain=True)
    print(
        "forecast model:",
        registry.forecast.metrics,
        "trained",
        registry.forecast.trained_at,
    )
    print("anomaly model trained", registry.anomaly.trained_at)


if __name__ == "__main__":
    main()
