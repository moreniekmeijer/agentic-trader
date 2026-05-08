from __future__ import annotations

from pydantic import BaseModel

from agentic_trader.services.market_data.response import MultiTimeframeSnapshot


class BracketLevels(BaseModel):
    reference_price: float
    take_profit_price: float
    stop_loss_price: float
    risk_per_share: float
    source: str


def round_alpaca_price(value: float) -> float:
    if value <= 0:
        raise ValueError("Alpaca order prices must be positive")
    decimals = 2 if value >= 1 else 4
    return round(value, decimals)


class BracketPolicy:
    def __init__(
        self,
        *,
        atr_multiple=2.0,
        reward_risk: float = 2.0,
        min_risk_pct: float = 0.03,
        max_risk_pct: float = 0.08,
        fallback_risk_pct=0.05,
    ):
        self.atr_multiple = atr_multiple
        self.reward_risk = reward_risk
        self.min_risk_pct = min_risk_pct
        self.max_risk_pct = max_risk_pct
        self.fallback_risk_pct = fallback_risk_pct

    def from_snapshot(self, snapshot: MultiTimeframeSnapshot) -> BracketLevels:
        reference_price = snapshot.daily.price
        if reference_price is None or reference_price <= 0:
            raise ValueError(f"{snapshot.symbol}: cannot derive bracket levels without a valid price")

        atr = snapshot.daily.atr
        if atr is not None and atr > 0:
            raw_risk = atr * self.atr_multiple
            min_risk = reference_price * self.min_risk_pct
            max_risk = reference_price * self.max_risk_pct
            risk_per_share = min(max(raw_risk, min_risk), max_risk)
            source = "atr"
        else:
            risk_per_share = reference_price * self.fallback_risk_pct
            source = "fallback_pct"

        stop_loss = reference_price - risk_per_share
        take_profit = reference_price + (risk_per_share * self.reward_risk)

        return BracketLevels(
            reference_price=round_alpaca_price(reference_price),
            take_profit_price=round_alpaca_price(take_profit),
            stop_loss_price=round_alpaca_price(stop_loss),
            risk_per_share=round_alpaca_price(risk_per_share),
            source=source,
        )
