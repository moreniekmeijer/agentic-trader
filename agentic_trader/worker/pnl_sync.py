from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from agentic_trader.database.models import Trade
from agentic_trader.database.session import get_session

logger = logging.getLogger(__name__)


class PnlSyncJob:
    """
    Haalt gerealiseerde PnL op uit Alpaca en schrijft die naar de trades tabel.

    Alpaca berekent de PnL — wij slaan hem alleen op voor agent-analyse.
    Draait periodiek; trades zonder pnl worden opnieuw gecheckt.
    """

    def __init__(self, alpaca_controller):
        self.alpaca = alpaca_controller

    def run(self) -> None:
        logger.info("Running PnL sync job")

        with get_session() as session:
            open_trades = self._unsettled_trades(session)

            if not open_trades:
                logger.info("No unsettled trades")
                return

            logger.info(f"Syncing PnL for {len(open_trades)} trade(s)")

            # Haal Alpaca activities eenmalig op — niet per trade
            activities = self._fetch_activities()
            pnl_by_order = self._index_by_order(activities)

            settled = 0
            for trade in open_trades:
                pnl = pnl_by_order.get(trade.alpaca_order_id)  # ty:ignore[invalid-argument-type]
                if pnl is None:
                    continue  # positie nog open

                trade.pnl = pnl
                settled += 1
                logger.info(f"Synced PnL for {trade.symbol}: {pnl:+.2f}")

            session.commit()
            logger.info(f"PnL sync complete — {settled}/{len(open_trades)} settled")

    def _unsettled_trades(self, session: Session) -> list[Trade]:
        stmt = select(Trade).where(Trade.pnl.is_(None)).where(Trade.alpaca_order_id.isnot(None))
        return list(session.scalars(stmt).all())

    def _fetch_activities(self) -> list:
        activities = self.alpaca.get_fill_activities()
        if activities:
            logger.debug(f"Activity sample: {activities[0]}")
        return activities

    def _index_by_order(self, activities: list[dict]) -> dict[str, float]:
        """
        Bouwt een map van order_id → realized_pl.
        Alpaca vult realized_pl alleen in bij sluitende trades (SELL na BUY).
        """
        result = {}
        for activity in activities:
            order_id = activity.get("order_id")
            realized_pl = activity.get("realized_pl")

            if order_id and realized_pl is not None:
                result[str(order_id)] = float(realized_pl)

        return result
