from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from agentic_trader.api.dependencies import get_db
from agentic_trader.api.schemas import (
    BrokerSnapshotResponse,
    LifecycleMismatchResponse,
    OrderLifecycleResponse,
    PositionLifecycleResponse,
)
from agentic_trader.database.models import PositionLifecycle, Trade
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


@router.get("/broker/positions", response_model=list[PositionLifecycleResponse])
@router.get("/positions", response_model=list[PositionLifecycleResponse], include_in_schema=False)
def get_position_lifecycles(status: str | None = None, session: Session = Depends(get_db)):
    """Return persisted broker position lifecycle rows, not live Alpaca positions."""
    repo = BrokerRepository(session)
    return repo.list_position_lifecycles(status=status)


@router.get("/broker/current-positions", response_model=list[PositionLifecycleResponse])
def get_current_position_lifecycles(session: Session = Depends(get_db)):
    """Return persisted broker positions that are currently open."""
    repo = BrokerRepository(session)
    return repo.list_position_lifecycles(status="open")


@router.get("/broker/lifecycle-mismatches", response_model=list[LifecycleMismatchResponse])
def get_lifecycle_mismatches(
    limit: int = Query(default=100, gt=0, le=500),
    session: Session = Depends(get_db),
) -> list[LifecycleMismatchResponse]:
    """Return local lifecycle records that require operator attention."""
    mismatches: list[LifecycleMismatchResponse] = []
    positions = (
        session.query(PositionLifecycle)
        .filter(PositionLifecycle.status != "open")
        .order_by(PositionLifecycle.last_broker_seen_at.desc())
        .limit(limit)
        .all()
    )
    for position in positions:
        mismatches.append(
            LifecycleMismatchResponse(
                source="position_lifecycle",
                source_id=position.id,
                symbol=position.symbol,
                status=position.status,
                reason=f"Position lifecycle is {position.status}",
                detected_at=position.last_broker_seen_at,
            )
        )

    remaining = max(0, limit - len(mismatches))
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
