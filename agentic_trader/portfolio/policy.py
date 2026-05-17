from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field


class PortfolioPolicy(BaseModel):
    """Deterministic portfolio limits for swing-trading allocation."""

    target_budget_eur: float = 10_000.0
    max_open_positions: int = 8
    min_cash_reserve_pct: float = Field(default=0.15, ge=0.0, le=1.0)
    max_position_pct: float = Field(default=0.18, ge=0.0, le=1.0)
    max_trade_risk_pct: float = Field(default=0.01, ge=0.0, le=1.0)
    max_sector_pct: float = Field(default=0.35, ge=0.0, le=1.0)
    min_hold_days: int = 2
    max_hold_days: int = 100

    @classmethod
    def from_env(cls) -> "PortfolioPolicy":
        return cls(
            target_budget_eur=_env_float("TARGET_BUDGET_EUR", 10_000.0),
            max_open_positions=_env_int("MAX_OPEN_POSITIONS", 8),
            min_cash_reserve_pct=_env_float("MIN_CASH_RESERVE_PCT", 0.15),
            max_position_pct=_env_float("MAX_POSITION_PCT", 0.18),
            max_trade_risk_pct=_env_float("MAX_TRADE_RISK_PCT", 0.01),
            max_sector_pct=_env_float("MAX_SECTOR_PCT", 0.35),
            min_hold_days=_env_int("MIN_HOLD_DAYS", 2),
            max_hold_days=_env_int("MAX_HOLD_DAYS", 100),
        )

    def equity(self, account: Any) -> float:
        return _float_value(account, "equity", "portfolio_value")

    def cash(self, account: Any) -> float:
        return _float_value(account, "cash")

    def buying_power(self, account: Any) -> float:
        return _float_value(account, "buying_power", default=self.cash(account))

    def cash_reserve(self, account: Any) -> float:
        return self.equity(account) * self.min_cash_reserve_pct

    def available_cash_after_reserve(self, account: Any) -> float:
        cash_after_reserve = self.cash(account) - self.cash_reserve(account)
        return max(0.0, min(cash_after_reserve, self.buying_power(account)))

    def max_position_value(self, account: Any) -> float:
        return self.equity(account) * self.max_position_pct

    def max_trade_risk_value(self, account: Any) -> float:
        return self.equity(account) * self.max_trade_risk_pct

    def max_sector_value(self, account: Any) -> float:
        return self.equity(account) * self.max_sector_pct

    def position_count_allows_new_buy(self, positions: Sequence[Any], symbol: str) -> bool:
        if self.find_position(positions, symbol) is not None:
            return True
        return len(positions) < self.max_open_positions

    def sector_allows_value(self, account: Any, sector_value: float, order_value: float) -> bool:
        return sector_value + order_value <= self.max_sector_value(account)

    def find_position(self, positions: Sequence[Any], symbol: str) -> Any | None:
        symbol = symbol.upper()
        for position in positions:
            if self.position_symbol(position).upper() == symbol:
                return position
        return None

    def position_symbol(self, position: Any) -> str:
        return str(_raw_value(position, "symbol", default=""))

    def position_qty(self, position: Any) -> float:
        return _float_value(position, "qty", "quantity")

    def position_market_value(self, position: Any) -> float:
        market_value = _float_value(position, "market_value")
        if market_value:
            return abs(market_value)

        qty = abs(self.position_qty(position))
        price = _float_value(position, "current_price", "avg_entry_price")
        return qty * price

    def allowed_buy_qty(
        self,
        *,
        account: Any,
        positions: Sequence[Any] | None = None,
        symbol: str | None = None,
        entry_price: float,
        stop_loss_price: float,
        conviction: str | None = None,
        cash_available: float | None = None,
        current_position_value: float | None = None,
        sector_value: float = 0.0,
    ) -> float:
        if entry_price <= 0:
            return 0.0

        if cash_available is None:
            cash_available = self.available_cash_after_reserve(account)
        risk_per_share = abs(entry_price - stop_loss_price)
        if risk_per_share <= 0:
            return 0.0

        if current_position_value is None:
            current_position_value = 0.0
            if positions is not None and symbol is not None:
                position = self.find_position(positions, symbol)
                if position is not None:
                    current_position_value = self.position_market_value(position)

        risk_pct = min(_conviction_risk_pct(conviction), self.max_trade_risk_pct)
        risk_budget = self.equity(account) * risk_pct
        position_budget = max(0.0, self.max_position_value(account) - current_position_value)
        sector_budget = max(0.0, self.max_sector_value(account) - sector_value)
        value_budget = min(cash_available, position_budget, sector_budget)

        if value_budget <= 0 or risk_budget <= 0:
            return 0.0

        qty_by_cash = int(value_budget / entry_price)
        qty_by_risk = int(risk_budget / risk_per_share)
        return float(max(0, min(qty_by_cash, qty_by_risk)))

    def sector_values(
        self,
        positions: Sequence[Any],
        sector_by_symbol: Mapping[str, str] | None = None,
    ) -> dict[str, float]:
        if not sector_by_symbol:
            return {}

        totals: dict[str, float] = {}
        for position in positions:
            symbol = self.position_symbol(position).upper()
            sector = self.sector_for(symbol, sector_by_symbol)
            if not sector:
                continue
            totals[sector] = totals.get(sector, 0.0) + self.position_market_value(position)
        return totals

    def sector_for(self, symbol: str, sector_by_symbol: Mapping[str, str] | None) -> str | None:
        if not sector_by_symbol:
            return None
        return (
            sector_by_symbol.get(symbol.upper())
            or sector_by_symbol.get(symbol.lower())
            or sector_by_symbol.get(symbol)
        )


def _conviction_risk_pct(conviction: str | None) -> float:
    risk_map = {"LOW": 0.005, "MEDIUM": 0.01, "HIGH": 0.02}
    return risk_map.get((conviction or "LOW").upper(), 0.005)


def _float_value(obj: Any, *names: str, default: float = 0.0) -> float:
    for name in names:
        value = _raw_value(obj, name)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _raw_value(obj: Any, name: str, default: Any | None = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default
