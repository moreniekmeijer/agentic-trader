"""Pure conversion helpers for database-facing persistence code."""

from __future__ import annotations

from typing import Any


def extract_price(order: Any) -> float | None:
    """Extract the best available execution price from an Alpaca order-like object."""
    return (
        getattr(order, "filled_avg_price", None)
        or getattr(order, "avg_fill_price", None)
        or getattr(order, "price", None)
        or None
    )


def extract_order_id(order: Any) -> str | None:
    order_id = getattr(order, "id", None)
    return str(order_id) if order_id else None


def extract_qty(order: Any) -> float | None:
    qty = getattr(order, "qty", None) or getattr(order, "filled_qty", None)
    if qty is None:
        return None
    try:
        return float(qty)
    except (TypeError, ValueError):
        return None
