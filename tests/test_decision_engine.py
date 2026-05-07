from types import SimpleNamespace
from typing import Literal, cast

from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.decision.engine import DecisionEngine


class FakeSession:
    def add(self, _obj):
        return None

    def commit(self):
        return None

    def flush(self):
        return None


class FakeRepo:
    def __init__(self):
        self.decision = SimpleNamespace(id=42)

    def save_decision(self, _response):
        return self.decision


class FakeAlpaca:
    def __init__(self):
        self.last_client_order_id: str | None = None

    def has_open_orders(self, _symbol):
        return False

    def buy(self, _symbol, _qty, client_order_id=None):
        self.last_client_order_id = client_order_id
        return SimpleNamespace(id="order-1", filled_avg_price=100.0, client_order_id=client_order_id)

    def sell(self, _symbol, _qty, client_order_id=None):
        self.last_client_order_id = client_order_id
        return SimpleNamespace(id="order-2", filled_avg_price=100.0, client_order_id=client_order_id)

    def get_available_qty(self, _symbol):
        return 1


class FakeRisk:
    def can_trade(self, _response):
        return SimpleNamespace(allowed=True, reason=None)

    def get_allowed_qty(self, _symbol):
        return 1


def _response(signal: Literal["BUY", "SELL", "HOLD"]) -> AggregatedResponse:
    return AggregatedResponse(
        symbol="AAPL",
        signal=signal,
        confidence=0.9,
        reasoning=["ok"],
        votes=[],
    )


def test_execute_decision_uses_decision_id_as_client_order_id():
    alpaca = FakeAlpaca()
    session = cast(Session, FakeSession())
    engine = DecisionEngine(alpaca, FakeRisk(), session)
    engine.repo = FakeRepo()
    engine.execute_decision(_response("BUY"))

    assert alpaca.last_client_order_id == "42"
