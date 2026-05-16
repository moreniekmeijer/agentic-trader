from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agentic_trader.api.dependencies import get_db
from agentic_trader.api.schemas import (
    BrokerSnapshotResponse,
    OrderLifecycleResponse,
    PositionLifecycleResponse,
)
from agentic_trader.database.repositories.broker import BrokerRepository

router = APIRouter(tags=["broker"])


@router.get("/broker/snapshot", response_model=BrokerSnapshotResponse)
def get_broker_snapshot(session: Session = Depends(get_db)):
    repo = BrokerRepository(session)
    snapshot = repo.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Broker snapshot not found")

    return snapshot


@router.get("/orders", response_model=list[OrderLifecycleResponse])
def get_orders(symbol: str | None = None, limit: int = 100, session: Session = Depends(get_db)):
    repo = BrokerRepository(session)
    return repo.list_order_lifecycles(symbol=symbol, limit=limit)


@router.get("/positions", response_model=list[PositionLifecycleResponse])
def get_positions(status: str | None = None, session: Session = Depends(get_db)):
    repo = BrokerRepository(session)
    return repo.list_position_lifecycles(status=status)
