from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.database.models import Decision, OrderIntent
from agentic_trader.database.repositories.broker import BrokerRepository
from agentic_trader.database.repositories.order_intents import OrderIntentRepository
from agentic_trader.database.repositories.trades import TradeRepository
from agentic_trader.decision.bracket_policy import BracketPolicy
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
        self.intent_repo = OrderIntentRepository(session)
        self.broker_repo = BrokerRepository(session)
        self.executor = Executor(alpaca_controller)
        self.bracket_policy = BracketPolicy()

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

        result = self._create_order_intent(decision, response)

        if not result:
            logger.info(f"{response.symbol}: no order intent created")
            self.session.commit()
            return

        intent, intended_price = result

        if not _auto_submit_order_intents():
            logger.info("%s: order intent %s is pending manual approval", response.symbol, intent.id)
            self.session.commit()
            return

        self._submit_intent(decision, response, intent, intended_price)

    def execute_review_decision(self, decision, symbol: str) -> None:
        """
        Executes a PortfolioDecision (HOLD or CLOSE_EARLY).
        """
        logger.info(f"DecisionEngine received review for {symbol}: {decision.action}")

        if decision.action in {"EXIT", "CLOSE_EARLY", "REDUCE"}:
            qty = self.executor.alpaca.get_available_qty(symbol)
            if decision.action == "REDUCE":
                qty = qty / 2
            if qty <= 0:
                logger.info(
                    "%s: no available position quantity for review action %s",
                    symbol,
                    decision.action,
                )
                return

            intent = self.intent_repo.create_pending(
                symbol=symbol,
                side="sell",
                qty=qty,
                order_type="market",
                rationale="; ".join(decision.reasoning),
                data={
                    "validated": True,
                    "source": "position_review",
                    "review_action": decision.action,
                    "reasoning": decision.reasoning,
                },
            )
            if not _auto_submit_order_intents():
                logger.info(
                    "%s: review order intent %s is pending manual approval",
                    symbol,
                    intent.id,
                )
                self.session.commit()
                return

            self._submit_review_intent(symbol, intent)
        elif decision.action == "TIGHTEN_STOP":
            logger.info(
                "%s: TIGHTEN_STOP recorded by position review; broker stop amendment is not implemented yet.",
                symbol,
            )
        else:
            logger.info(f"{symbol}: Action is HOLD. Doing nothing.")
            return

    # -----------------------------------------------------------------------
    # ORDER INTENT CREATION
    # -----------------------------------------------------------------------

    def _create_order_intent(
        self,
        decision: Decision,
        response: AggregatedResponse,
    ) -> tuple[OrderIntent, float | None] | None:
        symbol = response.symbol

        # Check for open orders first to avoid "insufficient qty" errors
        if self.executor.has_open_orders(symbol):
            logger.info(f"{symbol}: already has open orders, skipping")
            self.repo.mark_blocked(decision, "open broker order exists")
            return None

        if response.signal == "BUY":
            if not response.conviction:
                logger.warning(f"{symbol}: Missing conviction. Cannot place order.")
                return None

            bracket = self.bracket_policy.validate_or_derive(
                symbol=symbol,
                entry_price=response.entry_price,
                stop_loss_price=response.stop_loss_price,
                take_profit_price=response.take_profit_price,
                expected_horizon_days=response.expected_horizon_days,
                market_snapshot=response.market_snapshot,
            )
            if not bracket.allowed or bracket.plan is None:
                logger.warning("%s: bracket rejected: %s", symbol, bracket.reason)
                return None

            qty = self.risk.get_allowed_qty(
                symbol, bracket.plan.entry_price, bracket.plan.stop_loss_price, response.conviction
            )
            if qty <= 0:
                logger.info(f"{symbol}: no qty allowed")
                return None

            intent = self.intent_repo.create_pending(
                symbol=symbol,
                side="buy",
                qty=qty,
                order_type="limit",
                rationale="; ".join(response.reasoning),
                data={
                    "validated": True,
                    "decision_id": decision.id,
                    "limit_price": bracket.plan.entry_price,
                    "stop_loss_price": bracket.plan.stop_loss_price,
                    "take_profit_price": bracket.plan.take_profit_price,
                    "bracket_source": bracket.plan.source,
                    "thesis": response.thesis,
                    "invalidation": response.invalidation,
                    "expected_horizon_days": response.expected_horizon_days,
                },
            )
            return intent, bracket.plan.entry_price

        if response.signal in {"SELL", "EXIT"}:
            qty = self.executor.alpaca.get_available_qty(symbol)
            if qty <= 0:
                logger.info(f"{symbol}: no available position to sell")
                return None
            intent = self.intent_repo.create_pending(
                symbol=symbol,
                side="sell",
                qty=qty,
                order_type="market",
                rationale="; ".join(response.reasoning),
                data={"validated": True, "decision_id": decision.id},
            )
            return intent, None

        return None

    # -----------------------------------------------------------------------
    # INTENT SUBMISSION AND PERSISTENCE
    # -----------------------------------------------------------------------

    def _submit_intent(
        self,
        decision: Decision,
        response: AggregatedResponse,
        intent: OrderIntent,
        intended_price: float | None,
    ) -> None:
        if not self._broker_snapshot_is_fresh():
            self.intent_repo.mark_blocked(intent, "broker snapshot is stale")
            self.session.commit()
            return

        try:
            self.intent_repo.mark_approved(intent)
            order_result = self.executor.submit_intent(intent)
            self.intent_repo.mark_submitted(intent, order_result)
        except Exception as exc:
            self.intent_repo.mark_failed(intent, str(exc))
            logger.error("Failed to submit order intent %s for %s: %s", intent.id, intent.symbol, exc)
            self.session.commit()
            return

        self._persist_trade(decision, response, order_result, intent.qty, intended_price)

    def _submit_review_intent(self, symbol: str, intent: OrderIntent) -> None:
        if not self._broker_snapshot_is_fresh():
            self.intent_repo.mark_blocked(intent, "broker snapshot is stale")
            self.session.commit()
            return

        try:
            self.intent_repo.mark_approved(intent)
            order = self.executor.submit_intent(intent)
            self.intent_repo.mark_submitted(intent, order)
            self.repo.record_close_order_submitted(symbol, order)
            self.session.commit()
        except Exception as exc:
            self.intent_repo.mark_failed(intent, str(exc))
            logger.error("Failed to submit review order intent %s for %s: %s", intent.id, symbol, exc)
            self.session.commit()

    def _persist_trade(self, decision, response, order_result, qty, intended_price) -> None:
        if qty is None:
            logger.warning("Order result for %s had no intent quantity; trade not saved", decision.symbol)
            return

        self.repo.mark_executed(
            decision,
            order_result=order_result,
            side=_trade_side(response.signal),
            qty=qty,
            intended_price=intended_price,
        )

        self.session.commit()

    def _broker_snapshot_is_fresh(self) -> bool:
        latest = self.broker_repo.latest_snapshot()
        if latest is None:
            return False

        fetched_at = latest.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()

        return age_seconds <= _broker_snapshot_max_age_seconds()


def _trade_side(signal: str) -> str:
    if signal in {"SELL", "EXIT", "REDUCE"}:
        return "sell"
    return "buy"


def _auto_submit_order_intents() -> bool:
    return os.getenv("ORDER_INTENT_AUTO_SUBMIT", "false").lower() in {"1", "true", "yes"}


def _broker_snapshot_max_age_seconds() -> int:
    try:
        return int(os.getenv("BROKER_SNAPSHOT_MAX_AGE_SECONDS", "300"))
    except ValueError:
        return 300
