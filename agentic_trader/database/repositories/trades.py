from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.database.models import AgentVote, Decision, Trade

logger = logging.getLogger(__name__)


class TradeRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_decision(self, response: AggregatedResponse) -> Decision:
        decision = Decision(
            symbol=response.symbol,
            signal=response.signal,
            confidence=response.confidence,
            reasoning=response.reasoning,
            executed=False,
            thesis=response.thesis,
            invalidation=response.invalidation,
            expected_horizon_days=response.expected_horizon_days,
            sector=_extract_sector(response.market_snapshot),
            setup_type=_infer_setup_type(response.market_snapshot),
            evidence=response.evidence,
            market_snapshot=response.market_snapshot,
            data={"conviction": response.conviction},
        )
        self.session.add(decision)
        self.session.flush()

        for vote in response.votes:
            self.session.add(
                AgentVote(
                    symbol=response.symbol,
                    agent=vote.agent,
                    signal=vote.signal,
                    confidence=vote.confidence,
                    reasoning=vote.reasoning,
                    weight=vote.weight,
                    decision_id=decision.id,
                )
            )

        return decision

    def mark_blocked(self, decision: Decision, reason: str) -> None:
        decision.blocked_reason = reason

    def close_trade(
        self,
        trade: Trade,
        close_price: float,
        closed_at: datetime | None = None,
    ) -> None:
        trade.closed_at = closed_at or datetime.now(timezone.utc)
        trade.close_price = close_price

        assert trade.price is not None
        trade.pnl = (close_price - trade.price) * trade.qty
        trade.pnl_pct = (close_price - trade.price) / trade.price
        logger.info("Trade closed: %s PnL=%.2f (%.1f%%)", trade.symbol, trade.pnl, trade.pnl_pct * 100)

    def get_last_buy_decision(self, symbol: str) -> Decision | None:
        return (
            self.session.query(Decision)
            .filter_by(symbol=symbol, signal="BUY")
            .order_by(Decision.timestamp.desc())
            .first()
        )


def _extract_sector(market_snapshot: dict | None) -> str | None:
    if not market_snapshot:
        return None

    sector = market_snapshot.get("sector")
    if sector:
        return str(sector)

    fundamentals = market_snapshot.get("fundamentals")
    if isinstance(fundamentals, dict) and fundamentals.get("sector"):
        return str(fundamentals["sector"])

    return None


def _infer_setup_type(market_snapshot: dict | None) -> str | None:
    if not market_snapshot:
        return None

    daily = market_snapshot.get("daily")
    if not isinstance(daily, dict):
        return None

    trend = daily.get("trend")
    if daily.get("rsi_cross_30"):
        return "rsi_reclaim"
    if trend == "BULLISH" and daily.get("volume_spike"):
        return "trend_volume"
    if trend:
        return str(trend).lower()

    return None
