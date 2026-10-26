"""FastAPI entrypoint.  Run from `project/`:  uv run uvicorn app.main:app --reload"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import APP_VERSION
from app.database import engine, init_db
from app.ml.registry import ModelRegistry, load_models
from app.routers import forecast, health, monitor

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.models = load_models(engine)
    yield
    engine.dispose()


app = FastAPI(
    title="V-Mart Retail Intelligence API",
    description="Dual-model ML backend for promo forecasting and live anomaly detection.",
    version=APP_VERSION,
    lifespan=lifespan,
)
# Defined up-front so /health can report 503 instead of erroring if startup is bypassed.
app.state.models = ModelRegistry()

app.include_router(forecast.router)
app.include_router(monitor.router)
app.include_router(health.router)
