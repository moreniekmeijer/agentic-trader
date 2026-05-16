from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from agentic_trader.database.models import WatchlistEntry

logger = logging.getLogger(__name__)


class WatchlistRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(
        self,
        symbol: str,
        added_by: str,
        thesis: str,
        invalidation: str,
        horizon: str,
        review_after: datetime | None = None,
    ) -> WatchlistEntry:
        entry = WatchlistEntry(
            symbol=symbol,
            added_by=added_by,
            thesis=thesis,
            invalidation=invalidation,
            horizon=horizon,
            review_after=review_after,
        )
        self.session.add(entry)
        self.session.commit()
        logger.info("Watchlist: added %s (%s) by %s", symbol, horizon, added_by)
        return entry

    def active_symbols(self) -> list[str]:
        return [e.symbol for e in self.session.query(WatchlistEntry).filter(WatchlistEntry.is_active).all()]

    def deactivate(self, symbol: str, reason: str) -> None:
        entry = (
            self.session.query(WatchlistEntry)
            .filter(WatchlistEntry.symbol == symbol, WatchlistEntry.is_active)
            .first()
        )
        if entry:
            entry.is_active = False
            entry.deactivated_at = datetime.now(timezone.utc)
            entry.deactivation_reason = reason
            self.session.commit()
            logger.info("Watchlist: deactivated %s - %s", symbol, reason)
