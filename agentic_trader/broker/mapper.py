from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agentic_trader.broker.models import BrokerAccount, BrokerFill, BrokerOrder, BrokerPosition


def to_broker_account(account: Any) -> BrokerAccount:
    return BrokerAccount(
        account_id=_optional_str(_get(account, "id", "account_id")),
        status=_optional_str(_get(account, "status")),
        currency=_optional_str(_get(account, "currency")),
        cash=_float(_get(account, "cash")),
        buying_power=_float(_get(account, "buying_power")),
        equity=_float(_get(account, "equity")),
        portfolio_value=_float(_get(account, "portfolio_value")),
        day_trade_count=_optional_int(_get(account, "daytrade_count", "day_trade_count")),
        pattern_day_trader=_optional_bool(_get(account, "pattern_day_trader")),
    )


def to_broker_position(position: Any) -> BrokerPosition:
    return BrokerPosition(
        symbol=str(_get(position, "symbol")).upper(),
        asset_id=_optional_str(_get(position, "asset_id")),
        qty=_float(_get(position, "qty")),
        side=_optional_str(_get(position, "side")),
        avg_entry_price=_optional_float(_get(position, "avg_entry_price")),
        market_value=_optional_float(_get(position, "market_value")),
        current_price=_optional_float(_get(position, "current_price")),
        cost_basis=_optional_float(_get(position, "cost_basis")),
        unrealized_pl=_optional_float(_get(position, "unrealized_pl")),
        unrealized_plpc=_optional_float(_get(position, "unrealized_plpc")),
    )


def to_broker_order(order: Any) -> BrokerOrder:
    return BrokerOrder(
        order_id=str(_get(order, "id")),
        client_order_id=_optional_str(_get(order, "client_order_id")),
        asset_id=_optional_str(_get(order, "asset_id")),
        symbol=str(_get(order, "symbol")).upper(),
        status=_enum_str(_get(order, "status")) or "unknown",
        side=_enum_str(_get(order, "side")),
        order_type=_enum_str(_get(order, "type", "order_type")),
        order_class=_enum_str(_get(order, "order_class")),
        time_in_force=_enum_str(_get(order, "time_in_force")),
        qty=_optional_float(_get(order, "qty")),
        filled_qty=_optional_float(_get(order, "filled_qty")),
        filled_avg_price=_optional_float(_get(order, "filled_avg_price")),
        limit_price=_optional_float(_get(order, "limit_price")),
        stop_price=_optional_float(_get(order, "stop_price")),
        leg_order_ids=_leg_order_ids(order),
        submitted_at=_optional_datetime(_get(order, "submitted_at")),
        updated_at=_optional_datetime(_get(order, "updated_at")),
    )


def to_broker_fill(activity: Any) -> BrokerFill:
    return BrokerFill(
        activity_id=_optional_str(_get(activity, "id", "activity_id")),
        order_id=_optional_str(_get(activity, "order_id")),
        client_order_id=_optional_str(_get(activity, "client_order_id")),
        symbol=str(_get(activity, "symbol")).upper(),
        side=_enum_str(_get(activity, "side")),
        qty=_float(_get(activity, "qty")),
        price=_float(_get(activity, "price")),
        transaction_time=_optional_datetime(_get(activity, "transaction_time", "date")),
        raw_activity_type=_optional_str(_get(activity, "activity_type")),
    )


def _get(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _leg_order_ids(order: Any) -> list[str]:
    legs = _get(order, "legs") or []
    return [str(order_id) for leg in legs if (order_id := _get(leg, "id")) is not None]


def _enum_str(value: Any) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    return str(raw).lower()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    return str(raw)


def _float(value: Any) -> float:
    converted = _optional_float(value)
    return converted if converted is not None else 0.0


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"true", "1", "yes"}


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return None
