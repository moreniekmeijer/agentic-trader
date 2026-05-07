from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from agentic_trader.database.models import Trade
from agentic_trader.database.session import get_session

logger = logging.getLogger(__name__)


class ReconciliationJob:
    """Reconciles local open trades with Alpaca positions."""

    def __init__(self, alpaca_controller):
        self.alpaca = alpaca_controller

    def run(self) -> None:
        logger.info("Running reconciliation job")

        with get_session() as session:
            unsettled = list(
                session.scalars(select(Trade).where(Trade.pnl.is_(None)).where(Trade.side == "buy")).all()
            )
            if not unsettled:
                logger.info("No unsettled trades to reconcile")
                return

            alpaca_symbols = {pos.symbol for pos in self.alpaca.get_positions()}
            reconciled = 0

            for trade in unsettled:
                if trade.symbol in alpaca_symbols:
                    continue

                trade.closed_at = datetime.now(timezone.utc)
                trade.close_price = trade.price
                trade.pnl = 0.0
                trade.pnl_pct = 0.0
                reconciled += 1
                logger.warning(f"Reconciled missing Alpaca position for {trade.symbol}")

            session.commit()
            logger.info(f"Reconciliation complete — {reconciled}/{len(unsettled)} adjusted")
