from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from agentic_trader.agents.technical.agent import TechnicalAgent
from agentic_trader.database.models import Trade
from agentic_trader.database.repository import TradeRepository
from agentic_trader.database.session import get_session
from agentic_trader.decision.bracket_policy import round_alpaca_price

logger = logging.getLogger(__name__)

ReviewAction = Literal["HOLD", "TIGHTEN_STOP", "LOWER_TAKE_PROFIT", "CLOSE"]


class PositionReviewDecision(BaseModel):
    symbol: str
    action: ReviewAction
    confidence: float
    reasoning: list[str]
    new_stop_loss_price: float | None = None
    new_take_profit_price: float | None = None


class TechnicalExitReviewer:
    def __init__(self, multi_engine, technical_agent_factory=TechnicalAgent):
        self.multi_engine = multi_engine
        self.technical_agent_factory = technical_agent_factory

    def review(self, trade: Trade, _position) -> PositionReviewDecision:
        try:
            snapshot = self.multi_engine.compute(trade.symbol)
        except Exception as exc:
            return self._hold(trade.symbol, f"Market data unavailable: {exc}")

        current_price = snapshot.daily.price
        if current_price is None or current_price <= 0:
            return self._hold(trade.symbol, "Current market price unavailable")

        agent = self.technical_agent_factory(
            symbol=trade.symbol,
            buy_threshold=0.3,
            sell_threshold=0.3,
        )
        technical = agent.generate_signal(snapshot)
        if technical.signal in {"BUY", "HOLD"}:
            return self._hold(trade.symbol, "Technical signal does not support de-risking")
        if technical.confidence < 0.3:
            return self._hold(trade.symbol, "Technical sell signal below de-risk threshold")
        if trade.price is None:
            return self._hold(trade.symbol, "Entry price unavailable")

        if current_price > trade.price:
            return PositionReviewDecision(
                symbol=trade.symbol,
                action="LOWER_TAKE_PROFIT",
                confidence=technical.confidence,
                reasoning=technical.reasoning,
                new_take_profit_price=round_alpaca_price(current_price),
            )

        if trade.stop_loss_price is None:
            return self._hold(trade.symbol, "Stored stop-loss price unavailable")
        if current_price > trade.stop_loss_price:
            return PositionReviewDecision(
                symbol=trade.symbol,
                action="TIGHTEN_STOP",
                confidence=technical.confidence,
                reasoning=technical.reasoning,
                new_stop_loss_price=round_alpaca_price(max(trade.stop_loss_price, current_price * 0.98)),
            )

        return self._hold(trade.symbol, "No conservative de-risking action available")

    def _hold(self, symbol: str, reason: str) -> PositionReviewDecision:
        return PositionReviewDecision(
            symbol=symbol,
            action="HOLD",
            confidence=0.0,
            reasoning=[reason],
        )


def validate_de_risk_only(trade: Trade, decision: PositionReviewDecision) -> tuple[bool, str | None]:
    if decision.action == "HOLD":
        return True, None

    if decision.action == "CLOSE":
        if trade.qty <= 0:
            return False, "missing positive quantity"
        return True, None

    if decision.action == "TIGHTEN_STOP":
        if trade.stop_loss_price is None:
            return False, "missing bracket price"
        if decision.new_stop_loss_price is None:
            return False, "missing replacement price"
        if decision.new_stop_loss_price < trade.stop_loss_price:
            return False, "cannot lower stop-loss for long position"
        return True, None

    if decision.action == "LOWER_TAKE_PROFIT":
        if trade.take_profit_price is None:
            return False, "missing bracket price"
        if decision.new_take_profit_price is None:
            return False, "missing replacement price"
        if decision.new_take_profit_price > trade.take_profit_price:
            return False, "cannot raise take-profit for long position"
        return True, None

    return False, f"unsupported action {decision.action}"


class PositionReviewJob:
    def __init__(self, alpaca_controller, reviewer):
        self.alpaca = alpaca_controller
        self.reviewer = reviewer

    def run(self) -> None:
        logger.info("Running position review job")

        positions = {str(position.symbol): position for position in self.alpaca.get_positions()}

        with get_session() as session:
            repo = TradeRepository(session)
            trades = repo.open_bracketed_trades()

            for trade in trades:
                position = positions.get(trade.symbol)
                if position is None:
                    repo.record_bracket_event(
                        trade=trade,
                        event_type="state_mismatch",
                        reason="position missing in Alpaca",
                    )
                    continue

                decision = self.reviewer.review(trade, position)
                allowed, reason = validate_de_risk_only(trade, decision)
                if not allowed:
                    repo.record_bracket_event(
                        trade=trade,
                        event_type="review_rejected",
                        reason=reason,
                        confidence=decision.confidence,
                    )
                    continue

                self._apply_decision(repo, trade, decision)

    def _apply_decision(
        self,
        repo: TradeRepository,
        trade: Trade,
        decision: PositionReviewDecision,
    ) -> None:
        if decision.action == "HOLD":
            return

        try:
            if decision.action == "TIGHTEN_STOP":
                self._replace_stop(repo, trade, decision)
            elif decision.action == "LOWER_TAKE_PROFIT":
                self._replace_take_profit(repo, trade, decision)
            elif decision.action == "CLOSE":
                self._close_position(repo, trade, decision)
        except Exception as exc:
            repo.record_bracket_event(
                trade=trade,
                event_type="action_failed",
                reason=str(exc),
                confidence=decision.confidence,
            )

    def _replace_stop(
        self,
        repo: TradeRepository,
        trade: Trade,
        decision: PositionReviewDecision,
    ) -> None:
        if trade.stop_loss_order_id is None or decision.new_stop_loss_price is None:
            repo.record_bracket_event(
                trade=trade,
                event_type="state_mismatch",
                reason="missing active stop-loss order",
                confidence=decision.confidence,
            )
            return

        current_order_id = trade.stop_loss_order_id
        assert current_order_id is not None
        replacement = self.alpaca.replace_order(
            current_order_id,
            stop_price=decision.new_stop_loss_price,
        )
        new_order_id = _extract_order_id(replacement, fallback=current_order_id) or current_order_id
        old_price = trade.stop_loss_price
        repo.update_stop_loss_leg(
            trade,
            order_id=new_order_id,
            price=decision.new_stop_loss_price,
        )
        repo.record_bracket_event(
            trade=trade,
            event_type="stop_replaced",
            stop_loss_order_id=new_order_id,
            old_stop_loss_price=old_price,
            new_stop_loss_price=decision.new_stop_loss_price,
            reason="; ".join(decision.reasoning),
            confidence=decision.confidence,
            raw_response={"replacement_order_id": new_order_id},
        )

    def _replace_take_profit(
        self,
        repo: TradeRepository,
        trade: Trade,
        decision: PositionReviewDecision,
    ) -> None:
        if trade.take_profit_order_id is None or decision.new_take_profit_price is None:
            repo.record_bracket_event(
                trade=trade,
                event_type="state_mismatch",
                reason="missing active take-profit order",
                confidence=decision.confidence,
            )
            return

        current_order_id = trade.take_profit_order_id
        assert current_order_id is not None
        replacement = self.alpaca.replace_order(
            current_order_id,
            limit_price=decision.new_take_profit_price,
        )
        new_order_id = _extract_order_id(replacement, fallback=current_order_id) or current_order_id
        old_price = trade.take_profit_price
        repo.update_take_profit_leg(
            trade,
            order_id=new_order_id,
            price=decision.new_take_profit_price,
        )
        repo.record_bracket_event(
            trade=trade,
            event_type="take_profit_replaced",
            take_profit_order_id=new_order_id,
            old_take_profit_price=old_price,
            new_take_profit_price=decision.new_take_profit_price,
            reason="; ".join(decision.reasoning),
            confidence=decision.confidence,
            raw_response={"replacement_order_id": new_order_id},
        )

    def _close_position(
        self,
        repo: TradeRepository,
        trade: Trade,
        decision: PositionReviewDecision,
    ) -> None:
        available_qty = self.alpaca.get_available_qty(trade.symbol)
        if available_qty <= 0:
            repo.record_bracket_event(
                trade=trade,
                event_type="state_mismatch",
                reason="no available quantity to close",
                confidence=decision.confidence,
            )
            return

        qty = min(trade.qty, available_qty)
        order = self.alpaca.sell(trade.symbol, qty)
        order_id = _extract_order_id(order)
        repo.record_bracket_event(
            trade=trade,
            event_type="early_close_submitted",
            alpaca_order_id=order_id,
            reason="; ".join(decision.reasoning),
            confidence=decision.confidence,
            raw_response={"close_order_id": order_id, "qty": qty},
        )


def _extract_order_id(order, fallback: str | None = None) -> str | None:
    order_id = getattr(order, "id", fallback)
    return str(order_id) if order_id is not None else None
