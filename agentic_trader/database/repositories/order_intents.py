from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from agentic_trader.database.mapper import extract_order_id
from agentic_trader.database.models import OrderIntent


class OrderIntentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_pending(
        self,
        *,
        symbol: str,
        side: str,
        qty: float | None,
        order_type: str,
        rationale: str,
        data: dict[str, Any] | None = None,
    ) -> OrderIntent:
        intent = OrderIntent(
            symbol=symbol.upper(),
            side=side.lower(),
            qty=qty,
            order_type=order_type,
            status="pending_approval",
            rationale=rationale,
            data=data or {},
        )
        self.session.add(intent)
        self.session.flush()
        intent.client_order_id = _client_order_id(intent)
        self.session.flush()

        return intent

    def mark_approved(self, intent: OrderIntent) -> None:
        intent.status = "approved"

    def mark_submitted(self, intent: OrderIntent, order_result: Any) -> None:
        intent.status = "submitted"
        intent.submitted_at = datetime.now(timezone.utc)
        intent.broker_order_id = extract_order_id(order_result)
        intent.error = None

    def mark_failed(self, intent: OrderIntent, error: str) -> None:
        intent.status = "failed"
        intent.error = error

    def mark_blocked(self, intent: OrderIntent, reason: str) -> None:
        intent.status = "blocked"
        intent.error = reason


def _client_order_id(intent: OrderIntent) -> str:
    created_at = intent.created_at or datetime.now(timezone.utc)
    stamp = created_at.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"intent-{intent.id}-{intent.symbol.lower()}-{intent.side}-{stamp}"
