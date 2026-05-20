from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from agentic_trader.api.dependencies import get_db
from agentic_trader.api.schemas import (
    BrokerSnapshotResponse,
    LifecycleMismatchResponse,
    OrderLifecycleResponse,
)
from agentic_trader.database.models import Trade
from agentic_trader.database.repositories.broker import BrokerRepository

router = APIRouter(tags=["broker"])


@router.get("/broker/snapshot", response_model=BrokerSnapshotResponse)
def get_latest_broker_snapshot(session: Session = Depends(get_db)):
    """Return the latest persisted broker snapshot, not a live Alpaca read."""
    repo = BrokerRepository(session)
    snapshot = repo.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Broker snapshot not found")

    return snapshot


@router.get("/broker/orders", response_model=list[OrderLifecycleResponse])
@router.get("/orders", response_model=list[OrderLifecycleResponse], include_in_schema=False)
def get_order_lifecycles(
    symbol: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, gt=0, le=500),
    session: Session = Depends(get_db),
):
    """Return persisted broker order lifecycle rows, not live open orders."""
    repo = BrokerRepository(session)
    return repo.list_order_lifecycles(symbol=symbol, status=status, limit=limit)


@router.get("/broker/open-orders", response_model=list[OrderLifecycleResponse])
def get_open_order_lifecycles(
    symbol: str | None = None,
    limit: int = Query(default=100, gt=0, le=500),
    session: Session = Depends(get_db),
):
    """Return persisted broker orders that are still broker-open."""
    repo = BrokerRepository(session)
    return repo.list_open_order_lifecycles(symbol=symbol, limit=limit)





@router.get("/broker/lifecycle-mismatches", response_model=list[LifecycleMismatchResponse])
def get_lifecycle_mismatches(
    limit: int = Query(default=100, gt=0, le=500),
    session: Session = Depends(get_db),
) -> list[LifecycleMismatchResponse]:
    """Return local lifecycle records that require operator attention."""
    mismatches: list[LifecycleMismatchResponse] = []
    
    remaining = limit
    trades = (
        session.query(Trade)
        .filter(Trade.needs_reconciliation.is_(True))
        .order_by(Trade.timestamp.desc())
        .limit(remaining)
        .all()
    )
    for trade in trades:
        mismatches.append(
            LifecycleMismatchResponse(
                source="trade",
                source_id=trade.id,
                symbol=trade.symbol,
                status="needs_reconciliation",
                reason=trade.reconciliation_reason or "Trade requires reconciliation",
                detected_at=trade.closed_at or trade.timestamp,
            )
        )

    return mismatches
