from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.database.mapper import extract_order_id, extract_price, extract_qty
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

    def mark_executed(
        self,
        decision: Decision,
        order_result: Any,
        side: str,
        qty: float,
        intended_price: float | None = None,
    ) -> Trade:
        decision.executed = True
        price = extract_price(order_result) or intended_price

        trade = Trade(
            symbol=decision.symbol,
            side=side,
            qty=qty,
            price=price,
            alpaca_order_id=extract_order_id(order_result),
            decision_id=decision.id,
        )
        self.session.add(trade)
        logger.info("Trade saved: %s %sx %s @ %s", side, qty, decision.symbol, price)
        return trade

    def mark_blocked(self, decision: Decision, reason: str) -> None:
        decision.blocked_reason = reason

    def latest_open_buy_trade(self, symbol: str) -> Trade | None:
        return (
            self.session.query(Trade)
            .filter(Trade.symbol == symbol.upper(), Trade.side == "buy", Trade.closed_at.is_(None))
            .order_by(Trade.timestamp.desc())
            .first()
        )

    def record_close_order_submitted(self, symbol: str, order_result: Any) -> Trade | None:
        open_trade = self.latest_open_buy_trade(symbol)
        order_id = extract_order_id(order_result)
        qty = extract_qty(order_result) or (open_trade.qty if open_trade else None)
        if not qty or qty <= 0:
            logger.warning("Close order %s submitted for %s without a usable quantity", order_id, symbol)
            return None

        close_trade = Trade(
            symbol=symbol.upper(),
            side="sell",
            qty=qty,
            price=extract_price(order_result),
            alpaca_order_id=order_id,
            decision_id=None,
        )
        self.session.add(close_trade)
        logger.info(
            "Close order %s submitted for symbol=%s qty=%s; waiting for broker fill sync",
            order_id,
            symbol,
            qty,
        )
        return close_trade

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
