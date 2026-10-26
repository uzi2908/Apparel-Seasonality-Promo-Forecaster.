from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import VELOCITY_WINDOW_SECONDS
from app.database import LiveTransaction, get_db
from app.dependencies import get_anomaly_model
from app.ml.anomaly import CRITICAL, NORMAL, AnomalyModel
from app.schemas import AnomalyAlertResponse
from app.schemas import LiveTransaction as LiveTransactionIn

router = APIRouter(prefix="/api/v1", tags=["Live Monitoring"])


def _response(status: str, risk_level: str, is_anomaly: bool) -> AnomalyAlertResponse:
    return AnomalyAlertResponse(
        status=status,
        is_anomaly=is_anomaly,
        risk_level=risk_level,
        manager_action_required=risk_level == CRITICAL,
    )


@router.post("/transactions/monitor", response_model=AnomalyAlertResponse)
def monitor_live_sales(
    transaction: LiveTransactionIn,
    db: Session = Depends(get_db),
    model: AnomalyModel = Depends(get_anomaly_model),
):
    """
    Called every second by the Bash simulator. Combines the transaction's quantity
    with recent volume for the same store + product (from the DB) and scores it with
    the IsolationForest model. Every transaction is persisted with its verdict.
    Re-sending an existing `transaction_id` is idempotent (status "duplicate").
    """
    existing = db.scalar(
        select(LiveTransaction).where(
            LiveTransaction.transaction_id == transaction.transaction_id
        )
    )
    if existing is not None:
        return _response("duplicate", existing.risk_level, existing.is_anomaly)

    # Volume velocity: what this store already sold of this product in the last window.
    window_start = transaction.timestamp - timedelta(seconds=VELOCITY_WINDOW_SECONDS)
    prior_units, prior_txns = db.execute(
        select(
            func.coalesce(func.sum(LiveTransaction.quantity), 0),
            func.count(LiveTransaction.id),
        ).where(
            LiveTransaction.store_id == transaction.store_id,
            LiveTransaction.item_category == transaction.item_category,
            LiveTransaction.timestamp > window_start,
            LiveTransaction.timestamp <= transaction.timestamp,
        )
    ).one()
    velocity_units = int(prior_units) + transaction.quantity
    velocity_txns = int(prior_txns) + 1

    verdict = model.assess(
        transaction.item_category, transaction.quantity, velocity_units, velocity_txns
    )

    db.add(
        LiveTransaction(
            transaction_id=transaction.transaction_id,
            timestamp=transaction.timestamp,
            store_id=transaction.store_id,
            item_category=transaction.item_category,
            quantity=transaction.quantity,
            velocity_units=velocity_units,
            anomaly_score=verdict.score,
            is_anomaly=verdict.is_anomaly,
            risk_level=verdict.risk_level,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent request carrying the same transaction_id.
        db.rollback()
        return _response("duplicate", verdict.risk_level, verdict.is_anomaly)

    return _response("processed", verdict.risk_level, verdict.is_anomaly)
