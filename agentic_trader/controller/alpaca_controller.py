import os

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, StopLossRequest, TakeProfitRequest


class AlpacaController:
    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise ValueError("Missing Alpaca API credentials")

        self.client = TradingClient(api_key=self.api_key, secret_key=self.secret_key, paper=True)

    def get_account(self):
        return self.client.get_account()

    def get_positions(self):
        return self.client.get_all_positions()

    def get_position(self, symbol: str) -> float:
        try:
            positions = self.get_positions()
            for pos in positions:
                if pos.symbol == symbol:
                    return float(pos.qty)
            return 0.0
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return 0.0

    def get_available_qty(self, symbol: str) -> float:
        try:
            positions = self.get_positions()
            for pos in positions:
                if pos.symbol == symbol:
                    return float(pos.qty_available)
            return 0.0
        except Exception as e:
            print(f"Error fetching available qty: {e}")
            return 0.0

    def has_open_orders(self, symbol: str) -> bool:
        try:
            orders = self.get_orders()
            for order in orders:
                # Use string comparison to be safe across different Enum types
                status = str(order.status).lower()
                if order.symbol == symbol and status in ["open", "held", "new", "partially_filled"]:
                    return True
            return False
        except Exception as e:
            print(f"Error checking open orders: {e}")
            return False

    def get_orders(self):
        return self.client.get_orders()

    def sell(self, symbol: str, qty: float):
        """Helper to place a simple market sell order."""
        try:
            order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
            return self.client.submit_order(order)
        except Exception as e:
            print(f"[ERROR] Sell failed: {e}")
            raise

    def place_bracket_order(self, symbol: str, qty: float, side: str, limit_price: float, stop_loss_price: float, take_profit_price: float):
        try:
            order = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                limit_price=limit_price,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=take_profit_price),
                stop_loss=StopLossRequest(stop_price=stop_loss_price),
            )
            response = self.client.submit_order(order)
            return response
        except Exception as e:
            print(f"[ERROR] Bracket Order failed: {e}")
            raise

    def close_position(self, symbol: str):
        try:
            response = self.client.close_position(symbol_or_asset_id=symbol)
            return response
        except Exception as e:
            print(f"[ERROR] Failed to close position for {symbol}: {e}")
            raise
