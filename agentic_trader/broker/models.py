from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


BrokerIssueSeverity = Literal["warning", "error"]


class BrokerSyncIssue(BaseModel):
    severity: BrokerIssueSeverity
    code: str
    message: str
    symbol: str | None = None
    broker_id: str | None = None
    detected_at: datetime = Field(default_factory=utcnow)


class BrokerAccount(BaseModel):
    account_id: str | None
    status: str | None
    currency: str | None
    cash: float
    buying_power: float
    equity: float
    portfolio_value: float
    day_trade_count: int | None = None
    pattern_day_trader: bool | None = None


class BrokerPosition(BaseModel):
    symbol: str
    asset_id: str | None = None
    qty: float
    side: str | None = None
    avg_entry_price: float | None = None
    market_value: float | None = None
    current_price: float | None = None
    cost_basis: float | None = None
    unrealized_pl: float | None = None
    unrealized_plpc: float | None = None


class BrokerOrder(BaseModel):
    order_id: str
    client_order_id: str | None = None
    asset_id: str | None = None
    symbol: str
    status: str
    side: str | None = None
    order_type: str | None = None
    order_class: str | None = None
    time_in_force: str | None = None
    qty: float | None = None
    filled_qty: float | None = None
    filled_avg_price: float | None = None
    limit_price: float | None = None
    stop_price: float | None = None
    submitted_at: datetime | None = None
    updated_at: datetime | None = None


class BrokerFill(BaseModel):
    activity_id: str | None = None
    order_id: str | None = None
    client_order_id: str | None = None
    symbol: str
    side: str | None = None
    qty: float
    price: float
    transaction_time: datetime | None = None
    raw_activity_type: str | None = None


class BrokerSnapshot(BaseModel):
    fetched_at: datetime = Field(default_factory=utcnow)
    account: BrokerAccount
    positions: list[BrokerPosition] = Field(default_factory=list)
    open_orders: list[BrokerOrder] = Field(default_factory=list)
    recent_orders: list[BrokerOrder] = Field(default_factory=list)
    fills: list[BrokerFill] = Field(default_factory=list)
    issues: list[BrokerSyncIssue] = Field(default_factory=list)

    @property
    def invested_value(self) -> float:
        return sum(position.market_value or 0.0 for position in self.positions)

    @property
    def open_order_symbols(self) -> list[str]:
        return sorted({order.symbol for order in self.open_orders})

    @property
    def position_symbols(self) -> list[str]:
        return sorted({position.symbol for position in self.positions})
