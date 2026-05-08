"""
Repository: schrijft worker-output naar de database.
De worker kent alleen deze repository, niet de SQLAlchemy models direct.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.database.models import (
    AgentVote,
    BracketOrderEvent,
    Decision,
    Trade,
    WatchlistEntry,
    WorkerHeartbeat,
)

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
        take_profit_order_id: str | None = None,
        stop_loss_order_id: str | None = None,
        take_profit_price: float | None = None,
        stop_loss_price: float | None = None,
    ) -> Trade:
        """Markeert een decision als uitgevoerd en koppelt de trade."""
        decision.executed = True

        trade = Trade(
            symbol=decision.symbol,
            side=side,
            qty=qty,
            price=price,
            alpaca_order_id=alpaca_order_id,
            take_profit_order_id=take_profit_order_id,
            stop_loss_order_id=stop_loss_order_id,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
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

    def open_bracketed_trades(self) -> list[Trade]:
        stmt = (
            select(Trade)
            .where(Trade.pnl.is_(None))
            .where(Trade.side == "buy")
            .where(
                or_(
                    Trade.take_profit_order_id.isnot(None),
                    Trade.stop_loss_order_id.isnot(None),
                )
            )
        )
        return list(self.session.scalars(stmt).all())

    def record_bracket_event(
        self,
        *,
        trade: Trade,
        event_type: str,
        alpaca_order_id: str | None = None,
        take_profit_order_id: str | None = None,
        stop_loss_order_id: str | None = None,
        old_take_profit_price: float | None = None,
        new_take_profit_price: float | None = None,
        old_stop_loss_price: float | None = None,
        new_stop_loss_price: float | None = None,
        reason: str | None = None,
        confidence: float | None = None,
        raw_response: dict | None = None,
    ) -> BracketOrderEvent:
        event = BracketOrderEvent(
            trade=trade,
            symbol=trade.symbol,
            event_type=event_type,
            alpaca_order_id=alpaca_order_id,
            take_profit_order_id=take_profit_order_id,
            stop_loss_order_id=stop_loss_order_id,
            old_take_profit_price=old_take_profit_price,
            new_take_profit_price=new_take_profit_price,
            old_stop_loss_price=old_stop_loss_price,
            new_stop_loss_price=new_stop_loss_price,
            reason=reason,
            confidence=confidence,
            raw_response=raw_response,
        )
        self.session.add(event)
        return event

    def update_take_profit_leg(
        self,
        trade: Trade,
        *,
        order_id: str,
        price: float,
    ) -> None:
        trade.take_profit_order_id = order_id
        trade.take_profit_price = price

    def update_stop_loss_leg(
        self,
        trade: Trade,
        *,
        order_id: str,
        price: float,
    ) -> None:
        trade.stop_loss_order_id = order_id
        trade.stop_loss_price = price


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


class SystemRepository:
    def __init__(self, session: Session):
        self.session = session

    def update_heartbeat(self, symbols: list[str]) -> WorkerHeartbeat:
        heartbeat = self.get_last_heartbeat()
        if heartbeat is None:
            heartbeat = WorkerHeartbeat(id=1)
            self.session.add(heartbeat)

        heartbeat.last_seen = datetime.now(timezone.utc)
        heartbeat.active_symbols = sorted(set(symbols))
        self.session.flush()
        return heartbeat

    def get_last_heartbeat(self) -> WorkerHeartbeat | None:
        return self.session.get(WorkerHeartbeat, 1)
