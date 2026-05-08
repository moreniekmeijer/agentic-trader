from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.database.mapper import (
    extract_order_id,
    mark_decision_blocked,
    mark_decision_executed,
    to_trade,
)
from agentic_trader.database.repository import TradeRepository
from agentic_trader.decision.bracket_policy import BracketLevels

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

    def execute_decision(
        self,
        response: AggregatedResponse,
        bracket_levels: BracketLevels | None = None,
    ) -> None:
        decision = self.repo.save_decision(response)

        verdict = self.risk.can_trade(response)

        if not verdict.allowed:
            mark_decision_blocked(decision, verdict.reason or "unknown")
            logger.info(f"Risk blocked {response.symbol}: {verdict.reason}")
            self.session.commit()
            return

        result = self._execute_trade(
            response,
            client_order_id=self._build_client_order_id(decision, response),
            bracket_levels=bracket_levels,
        )

        if not result:
            logger.info(f"{response.symbol}: no trade executed")
            self.session.commit()
            return

        order_result, qty = result

        self._persist_trade(decision, response, order_result, qty, bracket_levels=bracket_levels)

    # -----------------------------------------------------------------------
    # TRADE EXECUTION (pure orchestration)
    # -----------------------------------------------------------------------

    def _execute_trade(
        self,
        response: AggregatedResponse,
        client_order_id: str,
        bracket_levels: BracketLevels | None = None,
    ):
        symbol = response.symbol

        # Check for open orders first to avoid "insufficient qty" errors
        if self.alpaca.has_open_orders(symbol):
            logger.info(f"{symbol}: already has open orders, skipping")
            return None

        if response.signal == "BUY":
            if bracket_levels is None:
                logger.info(f"{symbol}: missing bracket levels, skipping BUY")
                return None

            qty = self.risk.get_allowed_qty(symbol)
            if qty <= 0:
                logger.info(f"{symbol}: no qty allowed")
                return None
            order = self.alpaca.buy_bracket(
                symbol,
                qty,
                bracket_levels.take_profit_price,
                bracket_levels.stop_loss_price,
                client_order_id=client_order_id,
            )
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

    def _persist_trade(
        self,
        decision,
        response,
        order_result,
        qty,
        bracket_levels: BracketLevels | None = None,
    ) -> None:
        take_profit_order_id, stop_loss_order_id = self._extract_bracket_leg_ids(order_result)
        trade = to_trade(
            symbol=response.symbol,
            side=response.signal.lower(),
            qty=qty,
            order=order_result,
            decision_id=decision.id,
            take_profit_order_id=take_profit_order_id,
            stop_loss_order_id=stop_loss_order_id,
            take_profit_price=bracket_levels.take_profit_price if bracket_levels is not None else None,
            stop_loss_price=bracket_levels.stop_loss_price if bracket_levels is not None else None,
        )

        self.session.add(trade)
        self.session.flush()

        if bracket_levels is not None and hasattr(self.repo, "record_bracket_event"):
            self.repo.record_bracket_event(
                trade=trade,
                event_type="bracket_submitted",
                alpaca_order_id=trade.alpaca_order_id,
                take_profit_order_id=take_profit_order_id,
                stop_loss_order_id=stop_loss_order_id,
                new_take_profit_price=bracket_levels.take_profit_price,
                new_stop_loss_price=bracket_levels.stop_loss_price,
                raw_response={"parent_order_id": trade.alpaca_order_id},
            )

        mark_decision_executed(decision)

        self.session.commit()

        logger.info(f"Trade saved: {response.signal} {trade.qty} {response.symbol} @ {trade.price}")

    def _extract_bracket_leg_ids(self, order_result) -> tuple[str | None, str | None]:
        extractor = getattr(self.alpaca, "extract_bracket_leg_ids", None)
        if extractor is None:
            return None, None

        take_profit_order_id, stop_loss_order_id = extractor(order_result)
        if take_profit_order_id and stop_loss_order_id:
            return take_profit_order_id, stop_loss_order_id

        parent_order_id = extract_order_id(order_result)
        get_order = getattr(self.alpaca, "get_order", None)
        if not parent_order_id or get_order is None:
            return take_profit_order_id, stop_loss_order_id

        try:
            nested_order = get_order(parent_order_id, nested=True)
        except Exception as exc:
            logger.warning(f"{parent_order_id}: could not fetch nested bracket order: {exc}")
            return take_profit_order_id, stop_loss_order_id

        nested_take_profit_id, nested_stop_loss_id = extractor(nested_order)
        return (
            take_profit_order_id or nested_take_profit_id,
            stop_loss_order_id or nested_stop_loss_id,
        )

    def _build_client_order_id(self, decision, response: AggregatedResponse) -> str:
        timestamp = getattr(decision, "timestamp", None)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        compact_timestamp = timestamp.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        symbol = "".join(ch for ch in response.symbol.upper() if ch.isalnum())[:8]
        decision_id = str(decision.id)[-12:]

        return f"at-{symbol}-{decision_id}-{compact_timestamp}"[:48]
