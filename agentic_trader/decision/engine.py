from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.database.mapper import (
    mark_decision_blocked,
    mark_decision_executed,
    to_trade,
)
from agentic_trader.database.repository import TradeRepository

logger = logging.getLogger(__name__)


class DecisionEngine:
    def __init__(
        self,
        alpaca_controller,
        risk_engine,
        session: Session,
    ):
        self.alpaca = alpaca_controller
        self.risk = risk_engine
        self.session = session
        self.repo = TradeRepository(session)

    # -----------------------------------------------------------------------
    # MAIN FLOW
    # -----------------------------------------------------------------------

    def execute_decision(self, response: AggregatedResponse) -> None:
        decision = self.repo.save_decision(response)

        verdict = self.risk.can_trade(response)

        if not verdict.allowed:
            mark_decision_blocked(decision, verdict.reason or "unknown")
            logger.info(f"Risk blocked {response.symbol}: {verdict.reason}")
            self.session.commit()
            return

        result = self._execute_trade(response, client_order_id=str(decision.id))

        if not result:
            logger.info(f"{response.symbol}: no trade executed")
            self.session.commit()
            return

        order_result, qty = result

        self._persist_trade(decision, response, order_result, qty)

    # -----------------------------------------------------------------------
    # TRADE EXECUTION (pure orchestration)
    # -----------------------------------------------------------------------

    def _execute_trade(self, response: AggregatedResponse, client_order_id: str):
        symbol = response.symbol

        # Check for open orders first to avoid "insufficient qty" errors
        if self.alpaca.has_open_orders(symbol):
            logger.info(f"{symbol}: already has open orders, skipping")
            return None

        if response.signal == "BUY":
            qty = self.risk.get_allowed_qty(symbol)
            if qty <= 0:
                logger.info(f"{symbol}: no qty allowed")
                return None
            order = self.alpaca.buy(symbol, qty, client_order_id=client_order_id)
            if order is None:
                logger.info(f"{symbol}: no tradable Alpaca symbol found")
                return None
            return order, qty

        if response.signal == "SELL":
            qty = self.alpaca.get_available_qty(symbol)
            if qty <= 0:
                logger.info(f"{symbol}: no available position to sell")
                return None
            order = self.alpaca.sell(symbol, qty, client_order_id=client_order_id)
            if order is None:
                logger.info(f"{symbol}: no tradable Alpaca symbol found")
                return None
            return order, qty

        return None

    # -----------------------------------------------------------------------
    # PERSISTENCE
    # -----------------------------------------------------------------------

    def _persist_trade(self, decision, response, order_result, qty) -> None:
        trade = to_trade(
            symbol=response.symbol,
            side=response.signal.lower(),
            qty=qty,
            order=order_result,
            decision_id=decision.id,
        )

        self.session.add(trade)
        mark_decision_executed(decision)

        self.session.commit()

        logger.info(f"Trade saved: {response.signal} {trade.qty} {response.symbol} @ {trade.price}")
