from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.database.repositories.trades import TradeRepository
from agentic_trader.execution.executor import Executor

logger = logging.getLogger(__name__)


class DecisionEngine:
    def __init__(
        self,
        alpaca_controller,
        risk_engine,
        session: Session,
    ):
        self.risk = risk_engine
        self.session = session
        self.repo = TradeRepository(session)
        self.executor = Executor(alpaca_controller)

    # -----------------------------------------------------------------------
    # MAIN FLOW
    # -----------------------------------------------------------------------

    def execute_decision(self, response: AggregatedResponse) -> None:
        decision = self.repo.save_decision(response)

        verdict = self.risk.can_trade(response)

        if not verdict.allowed:
            self.repo.mark_blocked(decision, verdict.reason or "unknown")
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
                order = self.executor.close_position(symbol)
                order_id = getattr(order, "id", "unknown")
                logger.info(
                    f"{symbol}: Successfully closed position manually. Order ID: {order_id}"
                )
                self.repo.record_close_order_submitted(symbol, order)
                self.session.commit()
            except Exception as exc:
                logger.error(f"Failed to execute manual close for {symbol}: {exc}")
        else:
            logger.info(f"{symbol}: Action is HOLD. Doing nothing.")
            return

    # -----------------------------------------------------------------------
    # TRADE EXECUTION (pure orchestration)
    # -----------------------------------------------------------------------

    def _execute_trade(self, response: AggregatedResponse):
        symbol = response.symbol

        # Check for open orders first to avoid "insufficient qty" errors
        if self.executor.has_open_orders(symbol):
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

            order = self.executor.place_bracket_buy(
                symbol=symbol,
                qty=qty,
                limit_price=response.entry_price,
                stop_loss_price=response.stop_loss_price,
                take_profit_price=response.take_profit_price,
            )
            return order, qty

        if response.signal == "SELL":
            result = self.executor.sell_available_position(symbol)
            if result is None:
                logger.info(f"{symbol}: no available position to sell")
                return None
            return result

        return None

    # -----------------------------------------------------------------------
    # PERSISTENCE
    # -----------------------------------------------------------------------

    def _persist_trade(self, decision, response, order_result, qty) -> None:
        self.repo.mark_executed(
            decision,
            order_result=order_result,
            side=response.signal.lower(),
            qty=qty,
            intended_price=getattr(response, "entry_price", None),
        )

        self.session.commit()
