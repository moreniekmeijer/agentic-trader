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
    price: float
    alpaca_order_id: str | None
    closed_at: datetime | None
    close_price: float | None
    pnl: float | None
    pnl_pct: float | None
    decision_id: int | None


class AgentPerformanceResponse(BaseModel):
    model_config = {"from_attributes": True}

    agent: str
    signal: str
    count: int
    total_pnl: float
