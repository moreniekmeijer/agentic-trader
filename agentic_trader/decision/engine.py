import logging

logger = logging.getLogger(__name__)


class DecisionEngine:
    def __init__(self, alpaca_controller, risk_engine):
        self.alpaca = alpaca_controller
        self.risk = risk_engine

    def execute_decision(self, agent_response):
        symbol = agent_response.symbol

        # --- risk check ---
        if not self.risk.can_trade(agent_response):
            return None

        current_qty = self.alpaca.get_position(symbol)

        if agent_response.signal == "BUY":
            qty = self.risk.get_allowed_qty(symbol)

            if qty <= 0:
                logger.info(f"Risk: no qty allowed for {symbol}")
                return None

            result = self.alpaca.buy(symbol, qty)

        elif agent_response.signal == "SELL" and current_qty > 0:
            result = self.alpaca.sell(symbol, current_qty)

        else:
            logger.info(f"No trade for {symbol}")
            return None

        self.risk.register_trade(symbol)

        return result
