from types import SimpleNamespace

from alpaca.trading.enums import OrderClass

from agentic_trader.controller.alpaca_controller import AlpacaController


class FakeAsset:
    def __init__(self, tradable: bool):
        self.tradable = tradable


class FakeBracketClient:
    def __init__(self):
        self.submitted_order = None
        self.replaced_order_id = None
        self.replaced_order = None

    def get_asset(self, symbol: str):
        if symbol == "AAPL":
            return FakeAsset(tradable=True)
        raise AssertionError(f"Unexpected symbol lookup: {symbol}")

    def submit_order(self, order):
        self.submitted_order = order
        return SimpleNamespace(id="parent-1", symbol=order.symbol, filled_avg_price=100.0)

    def replace_order_by_id(self, order_id, order_data=None):
        self.replaced_order_id = order_id
        self.replaced_order = order_data
        return SimpleNamespace(id=f"{order_id}-replacement")


def _build_controller(client: FakeBracketClient) -> AlpacaController:
    controller = AlpacaController.__new__(AlpacaController)
    controller.api_key = "key"
    controller.secret_key = "secret"
    controller.client = client
    controller._symbol_cache = {}
    return controller


def test_buy_bracket_submits_alpaca_bracket_request():
    client = FakeBracketClient()
    controller = _build_controller(client)

    order = controller.buy_bracket(
        "AAPL",
        1,
        take_profit_price=112.0,
        stop_loss_price=94.0,
        client_order_id="decision-1",
    )

    assert order is not None
    assert client.submitted_order is not None
    assert client.submitted_order.order_class == OrderClass.BRACKET
    assert client.submitted_order.take_profit.limit_price == 112.0
    assert client.submitted_order.stop_loss.stop_price == 94.0
    assert client.submitted_order.client_order_id == "decision-1"


def test_extract_bracket_leg_ids_reads_nested_legs():
    controller = _build_controller(FakeBracketClient())
    order = SimpleNamespace(
        legs=[
            SimpleNamespace(id="tp-1", type="limit"),
            SimpleNamespace(id="sl-1", type="stop"),
        ]
    )

    assert controller.extract_bracket_leg_ids(order) == ("tp-1", "sl-1")


def test_replace_order_sends_limit_price():
    client = FakeBracketClient()
    controller = _build_controller(client)

    response = controller.replace_order("tp-1", limit_price=105.0)

    assert response.id == "tp-1-replacement"
    assert client.replaced_order_id == "tp-1"
    assert client.replaced_order is not None
    assert client.replaced_order.limit_price == 105.0
    assert client.replaced_order.stop_price is None


def test_replace_order_sends_stop_price():
    client = FakeBracketClient()
    controller = _build_controller(client)

    response = controller.replace_order("sl-1", stop_price=96.0)

    assert response.id == "sl-1-replacement"
    assert client.replaced_order_id == "sl-1"
    assert client.replaced_order is not None
    assert client.replaced_order.stop_price == 96.0
    assert client.replaced_order.limit_price is None
