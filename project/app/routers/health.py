import time

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from app.config import APP_VERSION
from app.database import engine

router = APIRouter(tags=["System"])


@router.get("/health")
def health_check(request: Request):
    """
    Readiness probe for load balancers / Kubernetes: models are in memory and the
    database answers a `SELECT 1`.
    """
    models = request.app.state.models
    forecast_loaded = models.forecast is not None
    anomaly_loaded = models.anomaly is not None

    start = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unreachable"
    db_latency_ms = round((time.perf_counter() - start) * 1000, 2)

    if not (forecast_loaded and anomaly_loaded) or db_status != "connected":
        raise HTTPException(
            status_code=503, detail="Service Unavailable: Components not ready"
        )

    return {
        "status": "healthy",
        "version": APP_VERSION,
        "components": {
            "database": {"status": db_status, "latency_ms": db_latency_ms},
            "forecast_model": "loaded",
            "anomaly_model": "loaded",
        },
    }
