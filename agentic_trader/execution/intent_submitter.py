from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from agentic_trader.database.models import OrderIntent
from agentic_trader.database.repositories.broker import BrokerRepository
from agentic_trader.database.repositories.order_intents import OrderIntentRepository
from agentic_trader.execution.controls import broker_submissions_enabled
from agentic_trader.execution.executor import Executor


class IntentSubmissionError(Exception):
    """Base class for expected order-intent submission failures."""


class BrokerSubmissionsDisabled(IntentSubmissionError):
    """Broker submissions are disabled by the runtime kill switch."""


class BrokerSnapshotStale(IntentSubmissionError):
    """The latest persisted broker snapshot is too old for safe execution."""


class IntentSubmissionFailed(IntentSubmissionError):
    """The broker rejected or failed an order-intent submission."""


class IntentSubmitter:
    def __init__(
        self,
        *,
        session: Session,
        alpaca_controller: Any,
        snapshot_max_age_seconds: int,
    ):
        self.session = session
        self.intent_repo = OrderIntentRepository(session)
        self.broker_repo = BrokerRepository(session)
        self.executor = Executor(alpaca_controller)
        self.snapshot_max_age_seconds = snapshot_max_age_seconds

    def submit(self, intent: OrderIntent) -> Any:
        if not broker_submissions_enabled():
            raise BrokerSubmissionsDisabled("broker submissions are disabled")

        if not self._broker_snapshot_is_fresh():
            self.intent_repo.mark_blocked(intent, "broker snapshot is stale")
            raise BrokerSnapshotStale("broker snapshot is stale")

        try:
            self.intent_repo.mark_approved(intent)
            order_result = self.executor.submit_intent(intent)
            self.intent_repo.mark_submitted(intent, order_result)
        except Exception as exc:
            self.intent_repo.mark_failed(intent, str(exc))
            raise IntentSubmissionFailed(str(exc)) from exc

        return order_result

    def _broker_snapshot_is_fresh(self) -> bool:
        latest = self.broker_repo.latest_snapshot()
        if latest is None:
            return False

        fetched_at = latest.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()

        return age_seconds <= self.snapshot_max_age_seconds
