from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BracketPlan(BaseModel):
    symbol: str
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    source: str

    @property
    def risk_per_share(self) -> float:
        return self.entry_price - self.stop_loss_price


class BracketVerdict(BaseModel):
    allowed: bool
    reason: str | None = None
    plan: BracketPlan | None = None


class BracketPolicy(BaseModel):
    """Validates or derives long-only swing-trade bracket prices."""

    min_hold_days: int = 2
    max_hold_days: int = 100
    min_stop_distance_pct: float = Field(default=0.01, ge=0.0)
    max_stop_distance_pct: float = Field(default=0.18, ge=0.0)
    min_reward_risk: float = Field(default=1.5, ge=0.0)
    atr_stop_multiple: float = Field(default=2.0, ge=0.0)
    atr_reward_multiple: float = Field(default=2.0, ge=0.0)

    def validate_or_derive(
        self,
        *,
        symbol: str,
        entry_price: float | None,
        stop_loss_price: float | None,
        take_profit_price: float | None,
        expected_horizon_days: int | None,
        market_snapshot: dict | None = None,
    ) -> BracketVerdict:
        if (
            expected_horizon_days is not None
            and not self.min_hold_days <= expected_horizon_days <= self.max_hold_days
        ):
            return BracketVerdict(allowed=False, reason="expected holding horizon is outside 2-100 days")

        entry = entry_price or _snapshot_value(market_snapshot, "daily", "price")
        if entry is None or entry <= 0:
            return BracketVerdict(allowed=False, reason="missing positive entry price")

        if stop_loss_price is not None and take_profit_price is not None:
            proposed = self._build_plan(
                symbol=symbol,
                entry_price=entry,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                source="llm_validated",
            )
            verdict = self._validate_plan(proposed, market_snapshot)
            if verdict.allowed:
                return verdict

        derived = self._derive_from_atr(symbol, entry, market_snapshot)
        if derived is None:
            return BracketVerdict(
                allowed=False,
                reason="bracket prices failed validation and ATR is unavailable",
            )

        return self._validate_plan(derived, market_snapshot)

    def _derive_from_atr(
        self,
        symbol: str,
        entry_price: float,
        market_snapshot: dict | None,
    ) -> BracketPlan | None:
        atr = _snapshot_value(market_snapshot, "daily", "atr")
        if atr is None or atr <= 0:
            return None

        risk_distance = atr * self.atr_stop_multiple
        return self._build_plan(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss_price=entry_price - risk_distance,
            take_profit_price=entry_price + risk_distance * self.atr_reward_multiple,
            source="atr_derived",
        )

    def _build_plan(
        self,
        *,
        symbol: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        source: str,
    ) -> BracketPlan:
        return BracketPlan(
            symbol=symbol,
            entry_price=_round_alpaca_price(entry_price),
            stop_loss_price=_round_alpaca_price(stop_loss_price),
            take_profit_price=_round_alpaca_price(take_profit_price),
            source=source,
        )

    def _validate_plan(self, plan: BracketPlan, market_snapshot: dict | None) -> BracketVerdict:
        if plan.stop_loss_price <= 0 or plan.take_profit_price <= 0:
            return BracketVerdict(allowed=False, reason="bracket prices must be positive")

        if not plan.stop_loss_price < plan.entry_price < plan.take_profit_price:
            return BracketVerdict(allowed=False, reason="long bracket must satisfy stop < entry < target")

        risk_distance = plan.entry_price - plan.stop_loss_price
        reward_distance = plan.take_profit_price - plan.entry_price
        min_risk_distance = plan.entry_price * self.min_stop_distance_pct
        atr = _snapshot_value(market_snapshot, "daily", "atr")
        if atr is not None and atr > 0:
            min_risk_distance = max(min_risk_distance, atr * 0.5)

        if risk_distance < min_risk_distance:
            return BracketVerdict(allowed=False, reason="stop loss is too close for swing-trade noise")

        if risk_distance > plan.entry_price * self.max_stop_distance_pct:
            return BracketVerdict(allowed=False, reason="stop loss is too wide for configured risk")

        if reward_distance / risk_distance < self.min_reward_risk:
            return BracketVerdict(allowed=False, reason="reward/risk is below policy minimum")

        return BracketVerdict(allowed=True, plan=plan)


def _round_alpaca_price(price: float) -> float:
    decimals = 4 if price < 1 else 2
    return round(price, decimals)


def _snapshot_value(snapshot: dict | None, timeframe: str, key: str) -> float | None:
    if not snapshot:
        return None

    block: Any = snapshot.get(timeframe) or {}
    value = block.get(key) if isinstance(block, dict) else getattr(block, key, None)
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None
