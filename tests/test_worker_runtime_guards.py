import json
from types import SimpleNamespace

import pandas as pd
from alpaca.common.exceptions import APIError

from agentic_trader.controller.alpaca_controller import AlpacaController
from agentic_trader.worker.models import TimeframeData
from agentic_trader.worker.worker import _env_int, _has_usable_timeframe_data


def _api_error(status_code: int, message: str) -> APIError:
    http_error = SimpleNamespace(response=SimpleNamespace(status_code=status_code), request=None)
    return APIError(json.dumps({"code": status_code, "message": message}), http_error)


class FakeAsset:
    def __init__(self, tradable: bool):
        self.tradable = tradable


class FakeClient:
    def __init__(self):
        self.submitted_symbol: str | None = None

    def get_asset(self, symbol: str):
        if symbol == "BRK-B":
            raise _api_error(404, "asset not found")
        if symbol == "BRK.B":
            return FakeAsset(tradable=True)
        raise _api_error(404, "asset not found")

    def submit_order(self, order):
        self.submitted_symbol = order.symbol
        return SimpleNamespace(id="order-1", symbol=order.symbol, filled_avg_price=100.0)


def _build_controller(client: FakeClient) -> AlpacaController:
    controller = AlpacaController.__new__(AlpacaController)
    controller.api_key = "key"
    controller.secret_key = "secret"
    controller.client = client
    controller._symbol_cache = {}
    return controller


def test_place_market_order_normalizes_symbol_for_alpaca():
    client = FakeClient()
    controller = _build_controller(client)

    order = controller.place_market_order("BRK-B", 1, "buy", client_order_id="123")

    assert order is not None
    assert client.submitted_symbol == "BRK.B"


def test_place_market_order_skips_untradable_symbol():
    client = FakeClient()
    controller = _build_controller(client)

    order = controller.place_market_order("UNKNOWN", 1, "buy", client_order_id="123")

    assert order is None
    assert client.submitted_symbol is None


def test_has_usable_timeframe_data_rejects_short_frames():
    short_frame = pd.DataFrame([{"close": 1.0}])
    valid_frame = pd.DataFrame([{"close": 1.0}, {"close": 2.0}])

    assert not _has_usable_timeframe_data(TimeframeData(daily=short_frame, h4=valid_frame))
    assert not _has_usable_timeframe_data(TimeframeData(daily=valid_frame, h4=short_frame))
    assert _has_usable_timeframe_data(TimeframeData(daily=valid_frame, h4=valid_frame))


def test_env_int_enforces_config_bounds(monkeypatch):
    monkeypatch.setenv("TEST_LIMIT", "0")
    assert _env_int("TEST_LIMIT", 5, min_value=1) == 5

    monkeypatch.setenv("TEST_LIMIT", "999")
    assert _env_int("TEST_LIMIT", 5, max_value=100) == 5

    monkeypatch.setenv("TEST_LIMIT", "42")
    assert _env_int("TEST_LIMIT", 5, min_value=1, max_value=100) == 42
