"""Loads (or trains on first run) the two models and holds them for the API process."""

import logging
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from app import config
from app.ml.anomaly import AnomalyModel
from app.ml.forecast import ForecastModel

log = logging.getLogger(__name__)


@dataclass
class ModelRegistry:
    forecast: ForecastModel | None = None
    anomaly: AnomalyModel | None = None

    @property
    def ready(self) -> bool:
        return self.forecast is not None and self.anomaly is not None


def load_models(engine: Engine, retrain: bool = False) -> ModelRegistry:
    """Use saved artefacts when present; otherwise train and save them."""
    registry = ModelRegistry()

    if not retrain and config.FORECAST_MODEL_PATH.exists():
        registry.forecast = ForecastModel.load(config.FORECAST_MODEL_PATH)
    else:
        log.info("Training forecast model from daily_sales ...")
        registry.forecast = ForecastModel.train(engine)
        registry.forecast.save(config.FORECAST_MODEL_PATH)

    if not retrain and config.ANOMALY_MODEL_PATH.exists():
        registry.anomaly = AnomalyModel.load(config.ANOMALY_MODEL_PATH)
    else:
        log.info("Training anomaly model ...")
        registry.anomaly = AnomalyModel.train()
        registry.anomaly.save(config.ANOMALY_MODEL_PATH)

    return registry
