from datetime import datetime
from typing import List

from pydantic import BaseModel


class WatchlistCreate(BaseModel):
    model_config = {"from_attributes": True}

    symbol: str
    thesis: str
    invalidation: str
    added_by: str | None = "manual"
    horizon: str | None = "medium"
    review_after: datetime | None = None


class WatchlistResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    symbol: str
    added_at: datetime
    added_by: str
    thesis: str
    invalidation: str
    horizon: str
    review_after: datetime | None


class AgentVoteResponse(BaseModel):
    model_config = {"from_attributes": True}

    agent: str
    signal: str
    confidence: float
    weight: float
    reasoning: List[str]


class DecisionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    symbol: str
    timestamp: datetime
    signal: str
    confidence: float
    reasoning: List[str]
    executed: bool
    blocked_reason: str | None
    votes: List[AgentVoteResponse]


class TradeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    symbol: str
    timestamp: datetime
    side: str
    qty: float
    price: float | None
    alpaca_order_id: str | None
    closed_at: datetime | None
    close_price: float | None
    pnl: float | None
    pnl_pct: float | None
    decision_id: int | None


class BrokerSnapshotResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    fetched_at: datetime
    account_id: str | None
    status: str | None
    currency: str | None
    cash: float
    buying_power: float
    equity: float
    portfolio_value: float
    invested_value: float
    position_count: int
    open_order_count: int
    issue_count: int
    data: dict


class OrderLifecycleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    broker_order_id: str
    client_order_id: str | None
    symbol: str
    side: str | None
    order_type: str | None
    order_class: str | None
    status: str
    qty: float | None
    filled_qty: float | None
    filled_avg_price: float | None
    limit_price: float | None
    stop_price: float | None
    submitted_at: datetime | None
    broker_updated_at: datetime | None
    last_seen_at: datetime


class PositionLifecycleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    symbol: str
    status: str
    opened_at: datetime | None
    closed_at: datetime | None
    qty: float
    avg_entry_price: float | None
    market_value: float | None
    current_price: float | None
    unrealized_pl: float | None
    unrealized_plpc: float | None
    thesis: str | None
    invalidation: str | None
    expected_horizon_days: int | None
    last_broker_seen_at: datetime


class AgentPerformanceResponse(BaseModel):
    model_config = {"from_attributes": True}

    agent: str
    signal: str
    count: int
    total_pnl: float
