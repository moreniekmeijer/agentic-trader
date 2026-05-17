import logging

from sqlalchemy.orm import Session

from agentic_trader.agents.reflector.agent import ReflectorAgent
from agentic_trader.controller.alpaca_controller import AlpacaController
from agentic_trader.learning.journal import LearningJournal

logger = logging.getLogger(__name__)


class ReflectorService:
    def __init__(self, session: Session, alpaca: AlpacaController):
        self.session = session
        self.alpaca = alpaca
        self.agent = ReflectorAgent()
        self.journal = LearningJournal(session)

    def run_reflection_cycle(self):
        """
        Scans for trades that are closed but not yet reflected upon.
        """
        logger.info("Scanning for closed trades to reflect on...")

        trades = self.journal.closed_trades_without_reflection()

        if not trades:
            logger.info("No new closed trades to reflect on.")
            return

        for trade in trades:
            logger.info(f"Reflecting on closed trade for {trade.symbol} (ID: {trade.id})")

            lesson = self.agent.reflect(trade, trade.decision)
            self.journal.record_reflection(trade, lesson)
            logger.info(f"Lesson learned for {trade.symbol}: {lesson}")

        self.session.commit()
