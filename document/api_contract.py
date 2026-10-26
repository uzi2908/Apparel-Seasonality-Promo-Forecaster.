from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
import time

app = FastAPI(
    title="V-Mart Retail Intelligence API",
    description="Dual-model ML backend for promo forecasting and live anomaly detection.",
    version="1.0.0"
)

# ---------------------------------------------------------
# 1. PYDANTIC SCHEMAS (The Data Contracts)
# ---------------------------------------------------------

# Schema for the Dashboard's "What-If" Promo Predictor
class PromoRequest(BaseModel):
    category: str = Field(..., example="Winter Jackets")
    base_price: float = Field(..., gt=0)
    proposed_discount_pct: float = Field(..., ge=0, le=100)
    is_festival_season: bool

class PromoResponse(BaseModel):
    predicted_units_sold: int
    projected_revenue: float
    confidence_interval_lower: float
    confidence_interval_upper: float

# Schema for the Bash Simulator's Live Transactions
class LiveTransaction(BaseModel):
    transaction_id: str
    timestamp: str
    store_id: str = Field(..., example="KANPUR_01")
    item_category: str
    quantity: int = Field(..., gt=0)

class AnomalyAlertResponse(BaseModel):
    status: str
    is_anomaly: bool
    risk_level: str = Field(..., description="'NORMAL', 'ELEVATED', or 'CRITICAL_PANIC_BUY'")
    manager_action_required: bool

# ---------------------------------------------------------
# 2. THE ENDPOINTS
# ---------------------------------------------------------

@app.post("/api/v1/forecast", response_model=PromoResponse, tags=["Forecasting"])
async def predict_promotion_impact(request: PromoRequest):
    """
    Called by the Streamlit Dashboard. 
    Passes slider inputs into the Regression model (e.g., RandomForest).
    """
    # Pseudo-code: prediction = forecast_model.predict(request)
    return {
        "predicted_units_sold": 450,
        "projected_revenue": 125000.00,
        "confidence_interval_lower": 400.00,
        "confidence_interval_upper": 510.00
    }

@app.post("/api/v1/transactions/monitor", response_model=AnomalyAlertResponse, tags=["Live Monitoring"])
async def monitor_live_sales(transaction: LiveTransaction):
    """
    Called every second by your Bash Script.
    Passes volume velocity to the Anomaly model (e.g., IsolationForest).
    """
    # Pseudo-code: anomaly_score = anomaly_model.predict(transaction.quantity over time)
    
    # Example logic tripwire
    if transaction.quantity > 50:
        return {
            "status": "processed",
            "is_anomaly": True,
            "risk_level": "CRITICAL_PANIC_BUY",
            "manager_action_required": True
        }
        
    return {
        "status": "processed",
        "is_anomaly": False,
        "risk_level": "NORMAL",
        "manager_action_required": False
    }

# ---------------------------------------------------------
# 3. ENTERPRISE HEALTH CHECK
# ---------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    """
    Used by load balancers (like AWS Route53 or Kubernetes) to check if the 
    server is actually ready to serve traffic, not just turned on.
    """
    # 1. Check if models are loaded in memory
    models_loaded = True # Replace with actual check: `if forecast_model is not None`
    
    # 2. Check Database connection latency
    start_time = time.time()
    db_status = "connected" # Replace with actual light DB ping (e.g. SELECT 1)
    db_latency_ms = round((time.time() - start_time) * 1000, 2)
    
    if not models_loaded or db_status != "connected":
        raise HTTPException(status_code=503, detail="Service Unavailable: Components not ready")
        
    return {
        "status": "healthy",
        "version": "1.0.0",
        "components": {
            "database": {"status": db_status, "latency_ms": db_latency_ms},
            "forecast_model": "loaded",
            "anomaly_model": "loaded"
        }
    }