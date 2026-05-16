from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.database.mapper import (
    mark_decision_blocked,
    mark_decision_executed,
    to_trade,
)
from agentic_trader.database.models import Trade
from agentic_trader.database.repositories.trades import TradeRepository

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

        result = self._execute_trade(response)

        if not result:
            logger.info(f"{response.symbol}: no trade executed")
            self.session.commit()
            return

        order_result, qty = result

        self._persist_trade(decision, response, order_result, qty)

    def execute_review_decision(self, decision, symbol: str) -> None:
        """
        Executes a PortfolioDecision (HOLD or CLOSE_EARLY).
        """
        logger.info(f"DecisionEngine received review for {symbol}: {decision.action}")

        if decision.action == "CLOSE_EARLY":
            logger.info(f"{symbol}: PortfolioAgent chose to CLOSE_EARLY. Executing market order to exit...")
            try:
                # Alpaca will cancel associated OCO bracket legs automatically when position is closed
                order = self.alpaca.close_position(symbol)
                order_id = getattr(order, "id", "unknown")
                logger.info(
                    f"{symbol}: Successfully closed position manually. Order ID: {order_id}"
                )

                # Update Trade in DB
                trade = (
                    self.session.query(Trade)
                    .filter_by(symbol=symbol, side="buy")
                    .order_by(Trade.timestamp.desc())
                    .first()
                )
                if trade:
                    # Logic for manual close status update can be added here
                    pass
            except Exception as e:
                logger.error(f"Failed to execute manual close for {symbol}: {e}")
        else:
            logger.info(f"{symbol}: Action is HOLD. Doing nothing.")
            return

    # -----------------------------------------------------------------------
    # TRADE EXECUTION (pure orchestration)
    # -----------------------------------------------------------------------

    def _execute_trade(self, response: AggregatedResponse):
        symbol = response.symbol

        # Check for open orders first to avoid "insufficient qty" errors
        if self.alpaca.has_open_orders(symbol):
            logger.info(f"{symbol}: already has open orders, skipping")
            return None

        if response.signal == "BUY":
            if (
                not response.entry_price
                or not response.stop_loss_price
                or not response.take_profit_price
                or not response.conviction
            ):
                logger.warning(f"{symbol}: Missing bracket targets or conviction. Cannot place order.")
                return None

            qty = self.risk.get_allowed_qty(
                symbol, response.entry_price, response.stop_loss_price, response.conviction
            )
            if qty <= 0:
                logger.info(f"{symbol}: no qty allowed")
                return None

            order = self.alpaca.place_bracket_order(
                symbol=symbol,
                qty=qty,
                side="buy",
                limit_price=response.entry_price,
                stop_loss_price=response.stop_loss_price,
                take_profit_price=response.take_profit_price,
            )
            return order, qty

        if response.signal == "SELL":
            qty = self.alpaca.get_available_qty(symbol)
            if qty <= 0:
                logger.info(f"{symbol}: no available position to sell")
                return None
            return self.alpaca.sell(symbol, qty), qty

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
            intended_price=getattr(response, "entry_price", None),
        )

        self.session.add(trade)
        mark_decision_executed(decision)

        self.session.commit()

        logger.info(f"Trade saved: {response.signal} {trade.qty} {response.symbol} @ {trade.price}")
