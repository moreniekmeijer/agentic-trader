from agents.technical.models import TechnicalAgentResponse
from execution.alpaca_controller import AlpacaController


class DecisionEngine:
    def __init__(self, alpaca_controller: AlpacaController, max_trade_qty: float = 1):
        self.controller = alpaca_controller
        self.max_trade_qty = max_trade_qty

    def execute_decision(self, agent_response: TechnicalAgentResponse):
        current_qty = self.controller.get_position(agent_response.symbol)

        if agent_response.signal == "BUY":
            qty = min(self.max_trade_qty, 1)  # max per trade
            print(f"Buying {qty} {agent_response.symbol} (currently have {current_qty})")
            return self.controller.buy(agent_response.symbol, qty)

        elif agent_response.signal == "SELL" and current_qty > 0:
            qty = min(self.max_trade_qty, current_qty)
            print(f"Selling {qty} {agent_response.symbol} (currently have {current_qty})")
            return self.controller.sell(agent_response.symbol, qty)

        else:
            print(
                f"No trade executed for {agent_response.symbol}, signal: {agent_response.signal}, current_qty: {current_qty}"
            )
            return None
