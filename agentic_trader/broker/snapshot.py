from __future__ import annotations

import logging
from datetime import datetime, timezone

from agentic_trader.broker.mapper import (
    to_broker_account,
    to_broker_fill,
    to_broker_order,
    to_broker_position,
)
from agentic_trader.broker.models import (
    BrokerFill,
    BrokerOrder,
    BrokerPosition,
    BrokerSnapshot,
    BrokerSyncIssue,
)

logger = logging.getLogger(__name__)


class BrokerSnapshotService:
    """Builds a typed, read-only view of Alpaca broker state."""

    def __init__(self, alpaca_controller):
        self.alpaca = alpaca_controller

    def fetch_snapshot(self) -> BrokerSnapshot:
        fetched_at = datetime.now(timezone.utc)
        issues: list[BrokerSyncIssue] = []

        account = to_broker_account(self.alpaca.get_account())
        positions = self._fetch_positions(issues)
        open_orders = self._fetch_orders(issues, open_only=True)
        recent_orders = self._fetch_orders(issues, open_only=False)
        fills = self._fetch_fills(issues)

        snapshot = BrokerSnapshot(
            fetched_at=fetched_at,
            account=account,
            positions=positions,
            open_orders=open_orders,
            recent_orders=recent_orders,
            fills=fills,
            issues=issues,
        )
        logger.info(
            "Broker snapshot fetched: equity=%.2f cash=%.2f positions=%d open_orders=%d issues=%d",
            snapshot.account.equity,
            snapshot.account.cash,
            len(snapshot.positions),
            len(snapshot.open_orders),
            len(snapshot.issues),
        )

        return snapshot

    def _fetch_positions(self, issues: list[BrokerSyncIssue]) -> list[BrokerPosition]:
        try:
            return [to_broker_position(position) for position in self.alpaca.get_positions()]
        except Exception as exc:
            issues.append(
                BrokerSyncIssue(
                    severity="error",
                    code="positions_fetch_failed",
                    message=str(exc),
                )
            )
            return []

    def _fetch_orders(self, issues: list[BrokerSyncIssue], *, open_only: bool) -> list[BrokerOrder]:
        try:
            raw_orders = self.alpaca.get_open_orders() if open_only else self.alpaca.get_recent_orders()
            return [to_broker_order(order) for order in raw_orders]
        except Exception as exc:
            issues.append(
                BrokerSyncIssue(
                    severity="error",
                    code="open_orders_fetch_failed" if open_only else "recent_orders_fetch_failed",
                    message=str(exc),
                )
            )
            return []

    def _fetch_fills(self, issues: list[BrokerSyncIssue]) -> list[BrokerFill]:
        try:
            return [to_broker_fill(activity) for activity in self.alpaca.get_fill_activities()]
        except Exception as exc:
            issues.append(
                BrokerSyncIssue(
                    severity="warning",
                    code="fills_fetch_failed",
                    message=str(exc),
                )
            )
            return []
