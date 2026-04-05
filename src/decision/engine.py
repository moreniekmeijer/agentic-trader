from agents.technical.models import TechnicalAgentResponse
from execution.alpaca_controller import AlpacaController


class DecisionEngine:
    def __init__(self, alpaca_controller: AlpacaController, max_trade_qty: float = 1):
        self.controller = alpaca_controller
        self.max_trade_qty = max_trade_qty

    def execute_decision(self, agent_response: TechnicalAgentResponse):
        if agent_response.signal == "HOLD":
            print(f"No action for {agent_response.symbol} (HOLD). Reason: {agent_response.reasoning}")
            return None

        qty = min(self.max_trade_qty, 1) # fixed quantity for now
        print(f"Executing {agent_response.signal} for {agent_response.symbol}, confidence {agent_response.confidence}")

        if agent_response.signal == "BUY":
            return self.controller.buy(agent_response.symbol, qty)
        elif agent_response.signal == "SELL":
            return self.controller.sell(agent_response.symbol, qty)

        return None