from __future__ import annotations

from typing import Any

from agentic_trader.database.models import OrderIntent


class Executor:
    """Places live broker orders through AlpacaController."""

    def __init__(self, alpaca_controller: Any):
        self.alpaca = alpaca_controller

    def has_open_orders(self, symbol: str) -> bool:
        return self.alpaca.has_open_orders(symbol)

    def place_bracket_buy(
        self,
        *,
        symbol: str,
        qty: float,
        limit_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        client_order_id: str | None = None,
    ) -> Any:
        return self.alpaca.place_bracket_order(
            symbol=symbol,
            qty=qty,
            side="buy",
            limit_price=limit_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            client_order_id=client_order_id,
        )

    def sell_available_position(
        self,
        symbol: str,
        *,
        qty: float | None = None,
        client_order_id: str | None = None,
    ) -> tuple[Any, float] | None:
        available_qty = self.alpaca.get_available_qty(symbol)
        if available_qty <= 0:
            return None

        qty = available_qty if qty is None else min(qty, available_qty)
        if qty <= 0:
            return None

        return self.alpaca.sell(symbol, qty, client_order_id=client_order_id), qty

    def close_position(self, symbol: str) -> Any:
        return self.alpaca.close_position(symbol)

    def submit_intent(self, intent: OrderIntent) -> Any:
        if intent.data is None or not intent.data.get("validated"):
            raise ValueError(f"OrderIntent {intent.id} is not validated")
        if intent.status != "approved":
            raise ValueError(f"OrderIntent {intent.id} must be approved before submission")
        if intent.qty is None or intent.qty <= 0:
            raise ValueError(f"OrderIntent {intent.id} has no executable quantity")
        if self.has_open_orders(intent.symbol):
            raise RuntimeError(f"{intent.symbol} already has an open broker order")

        if intent.side == "buy" and intent.order_type == "limit":
            stop_loss_price = intent.data.get("stop_loss_price")
            take_profit_price = intent.data.get("take_profit_price")
            limit_price = intent.data.get("limit_price")
            if not stop_loss_price or not take_profit_price or not limit_price:
                raise ValueError(f"OrderIntent {intent.id} is missing bracket prices")

            return self.place_bracket_buy(
                symbol=intent.symbol,
                qty=intent.qty,
                limit_price=limit_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                client_order_id=intent.client_order_id,
            )

        if intent.side == "sell" and intent.order_type == "market":
            result = self.sell_available_position(
                intent.symbol,
                qty=intent.qty,
                client_order_id=intent.client_order_id,
            )
            if result is None:
                raise RuntimeError(f"{intent.symbol} has no available quantity to sell")
            order, _ = result
            return order

        raise ValueError(f"Unsupported OrderIntent {intent.id}: {intent.side} {intent.order_type}")
