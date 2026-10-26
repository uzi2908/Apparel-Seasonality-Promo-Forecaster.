"""Pydantic data contracts (request/response bodies)."""

from datetime import date, datetime, timezone

from pydantic import BaseModel, Field, field_validator


# ---- Dashboard "What-If" promo predictor ------------------------------------
class PromoRequest(BaseModel):
    category: str = Field(..., examples=["Winter Jackets"])
    base_price: float = Field(..., gt=0)
    proposed_discount_pct: float = Field(..., ge=0, le=100)
    is_festival_season: bool
    forecast_date: date | None = Field(
        default=None,
        description="Optional day being planned for (drives seasonality, e.g. winter wear). Defaults to today.",
    )


class PromoResponse(BaseModel):
    predicted_units_sold: int
    projected_revenue: float
    confidence_interval_lower: float
    confidence_interval_upper: float


# ---- Bash simulator's live transactions -------------------------------------
class LiveTransaction(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=64)
    timestamp: datetime = Field(..., examples=["2026-10-26T10:15:30Z"])
    store_id: str = Field(..., min_length=1, max_length=64, examples=["KANPUR_01"])
    item_category: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(..., gt=0)

    @field_validator("timestamp")
    @classmethod
    def _to_naive_utc(cls, v: datetime) -> datetime:
        # Store/compare everything as naive UTC; naive input is assumed to be UTC.
        if v.tzinfo is not None:
            v = v.astimezone(timezone.utc).replace(tzinfo=None)
        return v


class AnomalyAlertResponse(BaseModel):
    status: str
    is_anomaly: bool
    risk_level: str = Field(
        ..., description="'NORMAL', 'ELEVATED', or 'CRITICAL_PANIC_BUY'"
    )
    manager_action_required: bool
