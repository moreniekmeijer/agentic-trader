import logging
from sqlalchemy.orm import Session
from agentic_trader.database.models import Trade, TradeJournal, Decision
from agentic_trader.agents.reflector.agent import ReflectorAgent
from agentic_trader.controller.alpaca_controller import AlpacaController

logger = logging.getLogger(__name__)

class ReflectorService:
    def __init__(self, session: Session, alpaca: AlpacaController):
        self.session = session
        self.alpaca = alpaca
        self.agent = ReflectorAgent()

    def run_reflection_cycle(self):
        """
        Scans for trades that are closed but not yet reflected upon.
        """
        logger.info("Scanning for closed trades to reflect on...")
        
        # 1. Fetch trades that don't have a journal entry yet
        trades = self.session.query(Trade).filter(
            ~Trade.id.in_(self.session.query(TradeJournal.trade_id))
        ).all()
        
        if not trades:
            logger.info("No new closed trades to reflect on.")
            return

        for trade in trades:
            # Check if trade is closed (has PNL)
            # If PNL is missing, try to fetch it from Alpaca if possible
            if trade.pnl is None:
                # This logic depends on how you track PNL. 
                # For now, we only reflect on trades where PNL was already synced.
                continue
                
            logger.info(f"Reflecting on closed trade for {trade.symbol} (ID: {trade.id})")
            
            # Fetch original decision reasoning
            decision = None
            if trade.decision_id:
                decision = self.session.query(Decision).filter_by(id=trade.decision_id).first()
            
            # Generate reflection via Agent
            lesson = self.agent.reflect(trade, decision)
            
            # Save to journal
            journal = TradeJournal(
                trade_id=trade.id,
                symbol=trade.symbol,
                reflection=lesson
            )
            self.session.add(journal)
            logger.info(f"Lesson learned for {trade.symbol}: {lesson}")

        self.session.commit()
