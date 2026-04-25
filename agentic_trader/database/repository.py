"""
Repository: schrijft worker-output naar de database.
De worker kent alleen deze repository, niet de SQLAlchemy models direct.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.database.models import AgentVote, Decision, Trade, WatchlistEntry

logger = logging.getLogger(__name__)


class TradeRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_decision(self, response: AggregatedResponse) -> Decision:
        """Slaat AggregatedResponse op met alle onderliggende votes."""
        decision = Decision(
            symbol=response.symbol,
            signal=response.signal,
            confidence=response.confidence,
            reasoning=response.reasoning,
            executed=False,
        )
        self.session.add(decision)
        self.session.flush()  # zodat decision.id beschikbaar is

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

    def mark_executed(
        self,
        decision: Decision,
        alpaca_order_id: str,
        side: str,
        qty: float,
        price: float | None,
    ) -> Trade:
        """Markeert een decision als uitgevoerd en koppelt de trade."""
        decision.executed = True

        trade = Trade(
            symbol=decision.symbol,
            side=side,
            qty=qty,
            price=price,
            alpaca_order_id=alpaca_order_id,
            decision_id=decision.id,
        )
        self.session.add(trade)
        logger.info(f"Trade saved: {side} {qty}x {decision.symbol} @ {price}")
        return trade

    def mark_blocked(self, decision: Decision, reason: str) -> None:
        """Logt waarom een decision geblokkeerd werd door de risk engine."""
        decision.blocked_reason = reason

    def close_trade(
        self,
        trade: Trade,
        close_price: float,
    ) -> None:
        """Vult PnL in bij sluiting van een positie."""
        trade.closed_at = datetime.now(timezone.utc)
        trade.close_price = close_price

        assert trade.price is not None
        trade.pnl = (close_price - trade.price) * trade.qty
        trade.pnl_pct = (close_price - trade.price) / trade.price
        logger.info(f"Trade closed: {trade.symbol} PnL={trade.pnl:.2f} ({trade.pnl_pct:.1%})")


class WatchlistRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(
        self,
        symbol: str,
        added_by: str,
        thesis: str,
        invalidation: str,
        horizon: str,
        review_after: datetime | None = None,
    ) -> WatchlistEntry:
        entry = WatchlistEntry(
            symbol=symbol,
            added_by=added_by,
            thesis=thesis,
            invalidation=invalidation,
            horizon=horizon,
            review_after=review_after,
        )
        self.session.add(entry)
        self.session.commit()
        logger.info(f"Watchlist: added {symbol} ({horizon}) by {added_by}")
        return entry

    def active_symbols(self) -> list[str]:
        return [e.symbol for e in self.session.query(WatchlistEntry).filter(WatchlistEntry.is_active).all()]

    def deactivate(self, symbol: str, reason: str) -> None:
        entry = (
            self.session.query(WatchlistEntry)
            .filter(WatchlistEntry.symbol == symbol, WatchlistEntry.is_active)
            .first()
        )
        if entry:
            entry.is_active = False
            entry.deactivated_at = datetime.now(timezone.utc)
            entry.deactivation_reason = reason
            self.session.commit()
            logger.info(f"Watchlist: deactivated {symbol} — {reason}")
