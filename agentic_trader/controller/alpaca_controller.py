import os
from datetime import datetime

import requests
from alpaca.broker import GetAccountActivitiesRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import ActivityType, OrderSide, OrderStatus, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest


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

    def get_fill_activities(self) -> list:
        """Haalt FILL activiteiten op via Alpaca REST API."""
        try:
            url = "https://paper-api.alpaca.markets/v2/account/activities/FILL"
            headers = {
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key,
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Could not fetch Alpaca activities: {e}")
            return []

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
