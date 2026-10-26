"""FastAPI dependencies that expose the shared, already-loaded models."""

from fastapi import HTTPException, Request

from app.ml.anomaly import AnomalyModel
from app.ml.forecast import ForecastModel


def get_forecast_model(request: Request) -> ForecastModel:
    model = request.app.state.models.forecast
    if model is None:
        raise HTTPException(status_code=503, detail="Forecast model not loaded")
    return model


def get_anomaly_model(request: Request) -> AnomalyModel:
    model = request.app.state.models.anomaly
    if model is None:
        raise HTTPException(status_code=503, detail="Anomaly model not loaded")
    return model
