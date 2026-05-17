from __future__ import annotations

from typing import Any


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
    ) -> Any:
        return self.alpaca.place_bracket_order(
            symbol=symbol,
            qty=qty,
            side="buy",
            limit_price=limit_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
        )

    def sell_available_position(self, symbol: str) -> tuple[Any, float] | None:
        qty = self.alpaca.get_available_qty(symbol)
        if qty <= 0:
            return None

        return self.alpaca.sell(symbol, qty), qty

    def close_position(self, symbol: str) -> Any:
        return self.alpaca.close_position(symbol)
