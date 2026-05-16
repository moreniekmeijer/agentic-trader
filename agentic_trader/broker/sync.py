from __future__ import annotations

import logging
from typing import Any

from agentic_trader.broker.models import BrokerSnapshot
from agentic_trader.broker.snapshot import BrokerSnapshotService
from agentic_trader.database.repositories.broker import BrokerRepository
from agentic_trader.database.session import get_session

logger = logging.getLogger(__name__)


def sync_broker_snapshot(alpaca_controller: Any) -> BrokerSnapshot | None:
    try:
        snapshot = BrokerSnapshotService(alpaca_controller).fetch_snapshot()
    except Exception as exc:
        logger.error("Broker snapshot failed: %s", exc, exc_info=True)
        return None

    with get_session() as session:
        BrokerRepository(session).save_snapshot(snapshot)

    if snapshot.issues:
        logger.warning(
            "Broker snapshot persisted with issues: %s",
            [issue.code for issue in snapshot.issues],
        )

    return snapshot
