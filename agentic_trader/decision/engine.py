import logging

from agentic_trader.agents.technical.models import TechnicalAgentResponse
from agentic_trader.risk.engine import RiskEngine

logger = logging.getLogger(__name__)


class DecisionEngine:
    def __init__(self, alpaca_controller, risk_engine: RiskEngine):
        self.alpaca = alpaca_controller
        self.risk = risk_engine

    def execute_decision(self, response: TechnicalAgentResponse) -> None:
        verdict = self.risk.can_trade(response)

        if not verdict.allowed:
            logger.info(f"Risk blocked {response.symbol}: {verdict.reason}")
            return

        symbol = response.symbol

        if response.signal == "BUY":
            qty = self.risk.get_allowed_qty(symbol)
            if qty <= 0:
                logger.info(f"{symbol}: no qty allowed by risk engine")
                return
            self.alpaca.buy(symbol, qty)

        elif response.signal == "SELL":
            current_qty = self.alpaca.get_position(symbol)
            if current_qty <= 0:
                logger.info(f"{symbol}: no position to sell")
                return
            self.alpaca.sell(symbol, current_qty)

        else:
            logger.info(f"{symbol}: HOLD, no action")
            return

        self.risk.register_trade(symbol)