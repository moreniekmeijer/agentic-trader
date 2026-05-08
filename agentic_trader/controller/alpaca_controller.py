import logging
import os

import requests
from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetOrderByIdRequest,
    GetOrdersRequest,
    MarketOrderRequest,
    ReplaceOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

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
            orders = self.get_orders(status=QueryOrderStatus.OPEN)
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

    def get_orders(self, status: QueryOrderStatus | None = None):
        request = GetOrdersRequest(status=status) if status is not None else None
        return self.client.get_orders(filter=request)

    def get_order(self, order_id: str, *, nested: bool = False):
        return self.client.get_order_by_id(order_id, filter=GetOrderByIdRequest(nested=nested))

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

    def place_bracket_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        take_profit_price: float,
        stop_loss_price: float,
        client_order_id: str | None = None,
    ):
        tradable_symbol = self.resolve_tradable_symbol(symbol)
        if tradable_symbol is None:
            logger.warning(f"{symbol}: not tradable through Alpaca, skipping bracket order submission")
            return None

        try:
            order = MarketOrderRequest(
                symbol=tradable_symbol,
                qty=qty,
                side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                client_order_id=client_order_id,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=take_profit_price),
                stop_loss=StopLossRequest(stop_price=stop_loss_price),
            )

            return self.client.submit_order(order)
        except Exception as e:
            print(f"[ERROR] Bracket order failed: {e}")
            raise

    def buy_bracket(
        self,
        symbol: str,
        qty: float,
        take_profit_price: float,
        stop_loss_price: float,
        client_order_id: str | None = None,
    ):
        return self.place_bracket_order(
            symbol,
            qty,
            "buy",
            take_profit_price,
            stop_loss_price,
            client_order_id=client_order_id,
        )

    def replace_order(
        self,
        order_id: str,
        *,
        limit_price: float | None = None,
        stop_price: float | None = None,
        client_order_id: str | None = None,
    ):
        request = ReplaceOrderRequest(
            limit_price=limit_price,
            stop_price=stop_price,
            client_order_id=client_order_id,
        )
        try:
            return self.client.replace_order_by_id(order_id, order_data=request)
        except Exception:
            logger.error(f"{order_id}: failed to replace Alpaca order", exc_info=True)
            raise

    def extract_bracket_leg_ids(self, order) -> tuple[str | None, str | None]:
        take_profit_order_id = None
        stop_loss_order_id = None

        for leg in getattr(order, "legs", None) or []:
            order_type = str(getattr(leg, "type", "")).lower()
            order_id = getattr(leg, "id", None)
            if order_id is None:
                continue

            if order_type == "limit" or "limit" in order_type:
                take_profit_order_id = str(order_id)
            elif "stop" in order_type:
                stop_loss_order_id = str(order_id)

        return take_profit_order_id, stop_loss_order_id
