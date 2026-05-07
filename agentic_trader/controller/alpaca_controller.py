import logging
import os

import requests
from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

logger = logging.getLogger(__name__)


class AlpacaController:
    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self._symbol_cache: dict[str, str | None] = {}

        if not self.api_key or not self.secret_key:
            raise ValueError("Missing Alpaca API credentials")

        self.client = TradingClient(api_key=self.api_key, secret_key=self.secret_key, paper=True)

    def get_account(self):
        return self.client.get_account()

    def _candidate_symbols(self, symbol: str) -> list[str]:
        candidates = [symbol.upper()]

        if "-" in symbol:
            candidates.append(symbol.replace("-", ".").upper())

        if "." in symbol:
            candidates.append(symbol.replace(".", "-").upper())

        return list(dict.fromkeys(candidates))

    def resolve_tradable_symbol(self, symbol: str) -> str | None:
        normalized_symbol = symbol.upper()
        if normalized_symbol in self._symbol_cache:
            return self._symbol_cache[normalized_symbol]

        for candidate in self._candidate_symbols(normalized_symbol):
            try:
                asset = self.client.get_asset(candidate)
            except APIError as exc:
                if exc.status_code == 404:
                    continue
                raise

            if getattr(asset, "tradable", False):
                self._symbol_cache[normalized_symbol] = candidate
                return candidate

        self._symbol_cache[normalized_symbol] = None
        return None

    def get_positions(self):
        return self.client.get_all_positions()

    def get_position(self, symbol: str) -> float:
        try:
            positions = self.get_positions()
            candidates = set(self._candidate_symbols(symbol))
            for pos in positions:
                if pos.symbol in candidates:
                    return float(pos.qty)
            return 0.0
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return 0.0

    def get_available_qty(self, symbol: str) -> float:
        try:
            positions = self.get_positions()
            candidates = set(self._candidate_symbols(symbol))
            for pos in positions:
                if pos.symbol in candidates:
                    return float(pos.qty_available)
            return 0.0
        except Exception as e:
            print(f"Error fetching available qty: {e}")
            return 0.0

    def has_open_orders(self, symbol: str) -> bool:
        try:
            orders = self.get_orders()
            candidates = set(self._candidate_symbols(symbol))
            for order in orders:
                # Use string comparison to be safe across different Enum types
                status = str(order.status).lower()
                if order.symbol in candidates and status in ["open", "held", "new", "partially_filled"]:
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

    def place_market_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        client_order_id: str | None = None,
    ):
        tradable_symbol = self.resolve_tradable_symbol(symbol)
        if tradable_symbol is None:
            logger.warning(f"{symbol}: not tradable through Alpaca, skipping order submission")
            return None

        try:
            order = MarketOrderRequest(
                symbol=tradable_symbol,
                qty=qty,
                side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                client_order_id=client_order_id,
            )

            response = self.client.submit_order(order)
            return response

        except Exception as e:
            print(f"[ERROR] Order failed: {e}")
            raise

    def buy(self, symbol: str, qty: float, client_order_id: str | None = None):
        return self.place_market_order(symbol, qty, "buy", client_order_id=client_order_id)

    def sell(self, symbol: str, qty: float, client_order_id: str | None = None):
        return self.place_market_order(symbol, qty, "sell", client_order_id=client_order_id)
