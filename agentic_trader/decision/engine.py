from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.database.models import Decision, OrderIntent
from agentic_trader.database.repositories.order_intents import OrderIntentRepository
from agentic_trader.database.repositories.trades import TradeRepository
from agentic_trader.decision.bracket_policy import BracketPolicy
from agentic_trader.execution.controls import (
    auto_submit_order_intents_enabled,
    broker_snapshot_max_age_seconds,
)
from agentic_trader.execution.executor import Executor
from agentic_trader.execution.intent_submitter import (
    BrokerSnapshotStale,
    BrokerSubmissionsDisabled,
    IntentSubmissionFailed,
    IntentSubmitter,
)

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
        self.executor = Executor(alpaca_controller)
        self.intent_submitter = IntentSubmitter(
            session=session,
            alpaca_controller=alpaca_controller,
            snapshot_max_age_seconds=broker_snapshot_max_age_seconds(),
        )
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

        intent = result

        if not auto_submit_order_intents_enabled():
            logger.info("%s: order intent %s is pending manual approval", response.symbol, intent.id)
            self.session.commit()
            return

        self._submit_intent(intent)

    def execute_review_decision(self, decision, symbol: str) -> None:
        """
        Executes a PortfolioDecision (HOLD or CLOSE_EARLY).
        """
        logger.info(f"DecisionEngine received review for {symbol}: {decision.action}")

        if decision.action in {"EXIT", "CLOSE_EARLY", "REDUCE"}:
            qty = self.executor.available_qty(symbol)
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
            if not auto_submit_order_intents_enabled():
                logger.info(
                    "%s: review order intent %s is pending manual approval",
                    symbol,
                    intent.id,
                )
                self.session.commit()
                return

            self._submit_intent(intent)
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
    ) -> OrderIntent | None:
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
            return intent

        if response.signal in {"SELL", "EXIT"}:
            qty = self.executor.available_qty(symbol)
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
            return intent

        return None

    # -----------------------------------------------------------------------
    # INTENT SUBMISSION AND PERSISTENCE
    # -----------------------------------------------------------------------

    def _submit_intent(self, intent: OrderIntent) -> None:
        try:
            self.intent_submitter.submit(intent)
        except BrokerSubmissionsDisabled:
            logger.warning("Broker submissions disabled; order intent %s remains pending", intent.id)
        except BrokerSnapshotStale:
            logger.warning("Order intent %s blocked because broker snapshot is stale", intent.id)
        except IntentSubmissionFailed as exc:
            logger.error("Failed to submit order intent %s for %s: %s", intent.id, intent.symbol, exc)

        self.session.commit()
