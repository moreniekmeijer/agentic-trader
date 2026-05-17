from datetime import datetime

from pydantic import BaseModel, Field

from agentic_trader.execution.controls import broker_mode as _broker_mode
from agentic_trader.execution.controls import broker_submissions_enabled as _broker_submissions_enabled


class AgentVoteResponse(BaseModel):
    model_config = {"from_attributes": True}

    agent: str
    signal: str
    confidence: float
    weight: float
    reasoning: list[str]


class DecisionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    symbol: str
    timestamp: datetime
    signal: str
    confidence: float
    reasoning: list[str]
    executed: bool
    blocked_reason: str | None
    thesis: str | None
    invalidation: str | None
    expected_horizon_days: int | None
    sector: str | None
    setup_type: str | None
    evidence: list[str]
    market_snapshot: dict | None
    votes: list[AgentVoteResponse]


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
    needs_reconciliation: bool
    reconciliation_reason: str | None
    decision_id: int | None


class BrokerSnapshotResponse(BaseModel):
    model_config = {"from_attributes": True}

    broker_mode: str = Field(default_factory=_broker_mode)
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

    broker_mode: str = Field(default_factory=_broker_mode)
    broker_submissions_enabled: bool = Field(default_factory=_broker_submissions_enabled)
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

    broker_mode: str = Field(default_factory=_broker_mode)
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


class OrderIntentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    created_at: datetime
    symbol: str
    side: str
    qty: float | None
    order_type: str
    status: str
    rationale: str | None
    client_order_id: str | None
    submitted_at: datetime | None
    broker_order_id: str | None
    error: str | None
    data: dict | None
    broker_mode: str
    broker_submissions_enabled: bool


class OrderIntentSubmissionResponse(BaseModel):
    intent: OrderIntentResponse


class ExecutionControlStatus(BaseModel):
    broker_mode: str
    paper_trading: bool
    broker_submissions_enabled: bool
    kill_switch_enabled: bool
    order_intent_auto_submit: bool


class KillSwitchRequest(BaseModel):
    enabled: bool


class LifecycleMismatchResponse(BaseModel):
    source: str
    source_id: int
    symbol: str | None
    status: str | None = None
    reason: str
    detected_at: datetime | None = None
