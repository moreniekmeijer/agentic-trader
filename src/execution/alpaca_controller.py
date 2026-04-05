import os

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest


class AlpacaController:
    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise ValueError("Missing Alpaca API credentials")

        # Paper trading = True (belangrijk!)
        self.client = TradingClient(api_key=self.api_key, secret_key=self.secret_key, paper=True)

    def get_account(self):
        return self.client.get_account()

    def get_positions(self):
        return self.client.get_all_positions()

    def get_orders(self):
        return self.client.get_orders()

    def place_market_order(self, symbol: str, qty: float, side: str):
        try:
            order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )

            response = self.client.submit_order(order)
            return response

        except Exception as e:
            print(f"[ERROR] Order failed: {e}")
            raise

    def buy(self, symbol: str, qty: float):
        return self.place_market_order(symbol, qty, "buy")

    def sell(self, symbol: str, qty: float):
        return self.place_market_order(symbol, qty, "sell")
