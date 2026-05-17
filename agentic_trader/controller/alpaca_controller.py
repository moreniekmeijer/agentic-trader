import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

logger = logging.getLogger(__name__)


class AlpacaController:
    """Live Alpaca broker adapter for account reads and order operations."""

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

    def get_open_orders(self):
        return self.get_orders(status=QueryOrderStatus.OPEN)

    def get_recent_orders(self, limit: int = 100):
        return self.get_orders(status=QueryOrderStatus.CLOSED, limit=limit)

    def get_position(self, symbol: str) -> float:
        try:
            positions = self.get_positions()
            for pos in positions:
                if pos.symbol == symbol:
                    return float(pos.qty)
            return 0.0
        except Exception as exc:
            logger.warning("Error fetching position for %s: %s", symbol, exc)
            return 0.0

    def get_available_qty(self, symbol: str) -> float:
        try:
            positions = self.get_positions()
            for pos in positions:
                if pos.symbol == symbol:
                    return float(pos.qty_available)
            return 0.0
        except Exception as exc:
            logger.warning("Error fetching available quantity for %s: %s", symbol, exc)
            return 0.0

    def has_open_orders(self, symbol: str) -> bool:
        try:
            orders = self.get_orders()
            for order in orders:
                status = getattr(order.status, "value", order.status)
                status = str(status).lower()
                if order.symbol == symbol and status in ["open", "held", "new", "partially_filled"]:
                    return True
            return False
        except Exception as exc:
            logger.warning("Error checking open orders for %s: %s", symbol, exc)
            return False

    def get_orders(self, status: QueryOrderStatus | None = None, limit: int | None = None):
        if status is None and limit is None:
            return self.client.get_orders()

        request_args = {}
        if status is not None:
            request_args["status"] = status
        if limit is not None:
            request_args["limit"] = limit

        request = GetOrdersRequest(**request_args)
        return self.client.get_orders(filter=request)

    def get_fill_activities(
        self,
        *,
        page_size: int = 100,
        after: datetime | None = None,
    ) -> list[dict[str, Any]]:
        query = {"page_size": str(page_size)}
        if after is not None:
            query["after"] = after.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        url = "https://paper-api.alpaca.markets/v2/account/activities/FILL"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        try:
            payload = self._get_json(url)
        except Exception:
            logger.error("Failed to fetch Alpaca fill activities", exc_info=True)
            raise

        if not isinstance(payload, list):
            return []

        return [activity for activity in payload if isinstance(activity, dict)]

    def sell(self, symbol: str, qty: float, client_order_id: str | None = None):
        """Helper to place a simple market sell order."""
        try:
            order_args = {
                "symbol": symbol,
                "qty": qty,
                "side": OrderSide.SELL,
                "time_in_force": TimeInForce.DAY,
            }
            if client_order_id:
                order_args["client_order_id"] = client_order_id

            order = MarketOrderRequest(**order_args)
            return self.client.submit_order(order)
        except Exception as exc:
            logger.error("Sell failed for %s: %s", symbol, exc, exc_info=True)
            raise

    def place_bracket_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        limit_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        client_order_id: str | None = None,
    ):
        try:
            order_args = {
                "symbol": symbol,
                "qty": qty,
                "side": OrderSide.BUY if side == "buy" else OrderSide.SELL,
                "time_in_force": TimeInForce.GTC,
                "limit_price": limit_price,
                "order_class": OrderClass.BRACKET,
                "take_profit": TakeProfitRequest(limit_price=take_profit_price),
                "stop_loss": StopLossRequest(stop_price=stop_loss_price),
            }
            if client_order_id:
                order_args["client_order_id"] = client_order_id

            order = LimitOrderRequest(**order_args)
            response = self.client.submit_order(order)
            return response
        except Exception as exc:
            logger.error("Bracket order failed for %s: %s", symbol, exc, exc_info=True)
            raise

    def get_news(self, symbol: str, limit: int = 5):
        from datetime import timedelta

        try:
            start = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
            url = f"https://data.alpaca.markets/v1beta1/news?symbols={symbol}&limit={limit}&start={start}"

            data = self._get_json(url)
            if not isinstance(data, dict):
                return []
            articles = data.get("news", [])

            return [
                {
                    "headline": a.get("headline", ""),
                    "summary": a.get("summary", ""),
                    "source": a.get("source", ""),
                    "url": a.get("url", ""),
                }
                for a in articles
            ]
        except Exception as exc:
            logger.warning("Direct news fetch failed for %s: %s", symbol, exc)
            return []

    def close_position(self, symbol: str):
        try:
            response = self.client.close_position(symbol_or_asset_id=symbol)
            return response
        except Exception as exc:
            logger.error("Failed to close position for %s: %s", symbol, exc, exc_info=True)
            raise

    def _get_json(self, url: str) -> Any:
        req = urllib.request.Request(url)
        req.add_header("APCA-API-KEY-ID", self.api_key)
        req.add_header("APCA-API-SECRET-KEY", self.secret_key)
        req.add_header("accept", "application/json")

        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
