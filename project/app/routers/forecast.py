from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_forecast_model
from app.ml.forecast import ForecastModel, UnknownCategoryError
from app.schemas import PromoRequest, PromoResponse

router = APIRouter(prefix="/api/v1", tags=["Forecasting"])


@router.post("/forecast", response_model=PromoResponse)
def predict_promotion_impact(
    request: PromoRequest, model: ForecastModel = Depends(get_forecast_model)
):
    """
    Called by the Streamlit dashboard. Slider inputs go into the RandomForest
    regression model; units are per daily sales record (category / price point / day).
    """
    try:
        result = model.predict(
            category=request.category,
            base_price=request.base_price,
            discount_pct=request.proposed_discount_pct,
            is_festival=request.is_festival_season,
            on_date=request.forecast_date or date.today(),
        )
    except UnknownCategoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    selling_price = request.base_price * (1 - request.proposed_discount_pct / 100)
    return PromoResponse(
        predicted_units_sold=result.units,
        projected_revenue=round(result.units * selling_price, 2),
        confidence_interval_lower=result.lower,
        confidence_interval_upper=result.upper,
    )
