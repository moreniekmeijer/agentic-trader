from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Literal, cast

from sqlalchemy.orm import Session

from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.database.models import Trade
from agentic_trader.decision.bracket_policy import BracketLevels
from agentic_trader.decision.engine import DecisionEngine


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, _obj):
        self.added.append(_obj)

    def commit(self):
        self.committed = True

    def flush(self):
        return None


class FakeRepo:
    def __init__(self):
        self.decision = SimpleNamespace(
            id=42,
            timestamp=datetime(2026, 5, 8, 13, 20, 32, 123456, tzinfo=timezone.utc),
        )
        self.bracket_events = []

    def save_decision(self, _response):
        return self.decision

    def record_bracket_event(self, **kwargs):
        self.bracket_events.append(kwargs)


class FakeAlpaca:
    def __init__(self):
        self.last_client_order_id: str | None = None
        self.buy_bracket_called = False
        self.buy_called = False
        self.sell_called = False

    def has_open_orders(self, _symbol):
        return False

    def buy(self, _symbol, _qty, client_order_id=None):
        self.buy_called = True
        self.last_client_order_id = client_order_id
        return SimpleNamespace(id="order-1", filled_avg_price=100.0, client_order_id=client_order_id)

    def buy_bracket(
        self,
        _symbol,
        _qty,
        take_profit_price,
        stop_loss_price,
        client_order_id=None,
    ):
        self.buy_bracket_called = True
        self.last_client_order_id = client_order_id
        self.last_take_profit_price = take_profit_price
        self.last_stop_loss_price = stop_loss_price
        return SimpleNamespace(
            id="parent-1",
            filled_avg_price=100.0,
            client_order_id=client_order_id,
            legs=[
                SimpleNamespace(id="tp-1", type="limit"),
                SimpleNamespace(id="sl-1", type="stop"),
            ],
        )

    def sell(self, _symbol, _qty, client_order_id=None):
        self.sell_called = True
        self.last_client_order_id = client_order_id
        return SimpleNamespace(id="order-2", filled_avg_price=100.0, client_order_id=client_order_id)

    def get_available_qty(self, _symbol):
        return 1

    def extract_bracket_leg_ids(self, order):
        take_profit_order_id = None
        stop_loss_order_id = None
        for leg in getattr(order, "legs", []) or []:
            if getattr(leg, "type", None) == "limit":
                take_profit_order_id = leg.id
            elif "stop" in getattr(leg, "type", ""):
                stop_loss_order_id = leg.id
        return take_profit_order_id, stop_loss_order_id


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


def _bracket_levels() -> BracketLevels:
    return BracketLevels(
        reference_price=100.0,
        take_profit_price=112.0,
        stop_loss_price=94.0,
        risk_per_share=6.0,
        source="atr",
    )


def test_execute_decision_uses_traceable_unique_client_order_id():
    alpaca = FakeAlpaca()
    session = cast(Session, FakeSession())
    engine = DecisionEngine(alpaca, FakeRisk(), session)
    engine.repo = FakeRepo()
    engine.execute_decision(_response("BUY"), bracket_levels=_bracket_levels())

    assert alpaca.last_client_order_id == "at-AAPL-42-20260508132032123456"
    assert len(alpaca.last_client_order_id) <= 48


def test_buy_decision_uses_bracket_order():
    alpaca = FakeAlpaca()
    session = cast(Session, FakeSession())
    engine = DecisionEngine(alpaca, FakeRisk(), session)
    engine.repo = FakeRepo()

    engine.execute_decision(_response("BUY"), bracket_levels=_bracket_levels())

    assert alpaca.buy_bracket_called
    assert not alpaca.buy_called
    assert alpaca.last_take_profit_price == 112.0
    assert alpaca.last_stop_loss_price == 94.0


def test_buy_without_bracket_levels_submits_no_order():
    alpaca = FakeAlpaca()
    session = cast(Session, FakeSession())
    engine = DecisionEngine(alpaca, FakeRisk(), session)
    engine.repo = FakeRepo()

    engine.execute_decision(_response("BUY"))

    assert not alpaca.buy_bracket_called
    assert not alpaca.buy_called


def test_sell_decision_still_uses_market_sell():
    alpaca = FakeAlpaca()
    session = cast(Session, FakeSession())
    engine = DecisionEngine(alpaca, FakeRisk(), session)
    engine.repo = FakeRepo()

    engine.execute_decision(_response("SELL"))

    assert alpaca.sell_called


def test_bracket_leg_ids_are_persisted_on_trade():
    alpaca = FakeAlpaca()
    fake_session = FakeSession()
    session = cast(Session, fake_session)
    repo = FakeRepo()
    engine = DecisionEngine(alpaca, FakeRisk(), session)
    engine.repo = repo

    engine.execute_decision(_response("BUY"), bracket_levels=_bracket_levels())

    trades = [item for item in fake_session.added if isinstance(item, Trade)]
    assert len(trades) == 1
    trade = trades[0]
    assert trade.alpaca_order_id == "parent-1"
    assert trade.take_profit_order_id == "tp-1"
    assert trade.stop_loss_order_id == "sl-1"
    assert trade.take_profit_price == 112.0
    assert trade.stop_loss_price == 94.0
    assert repo.bracket_events[0]["event_type"] == "bracket_submitted"
