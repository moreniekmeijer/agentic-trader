from contextlib import contextmanager
from types import SimpleNamespace
from typing import ClassVar

from agentic_trader.agents.models import AgentResponse
from agentic_trader.database.models import Trade
from agentic_trader.services.market_data.response import MarketDataSnapshot, MultiTimeframeSnapshot
from agentic_trader.worker import position_review as position_review_module
from agentic_trader.worker.position_review import (
    PositionReviewDecision,
    PositionReviewJob,
    ReviewAction,
    TechnicalExitReviewer,
    validate_de_risk_only,
)
from agentic_trader.worker.worker import _env_int


def _trade(**overrides) -> Trade:
    values = {
        "symbol": "AAPL",
        "side": "buy",
        "qty": 5.0,
        "price": 100.0,
        "alpaca_order_id": "parent-1",
        "take_profit_order_id": "tp-1",
        "stop_loss_order_id": "sl-1",
        "take_profit_price": 120.0,
        "stop_loss_price": 90.0,
    }
    values.update(overrides)
    return Trade(**values)


def _decision(
    action: ReviewAction,
    *,
    new_stop_loss_price: float | None = None,
    new_take_profit_price: float | None = None,
) -> PositionReviewDecision:
    return PositionReviewDecision(
        symbol="AAPL",
        action=action,
        confidence=0.6,
        reasoning=["risk off"],
        new_stop_loss_price=new_stop_loss_price,
        new_take_profit_price=new_take_profit_price,
    )


def _market(price: float) -> MultiTimeframeSnapshot:
    daily = MarketDataSnapshot(
        symbol="AAPL",
        price=price,
        rsi=None,
        rsi_prev=None,
        rsi_trend=None,
        rsi_cross_30=None,
        rsi_cross_70=None,
        ma_50=None,
        trend=None,
        volume=None,
        volume_avg=None,
        volume_spike=None,
    )
    return MultiTimeframeSnapshot(symbol="AAPL", daily=daily, h4=daily)


def test_validate_rejects_lower_stop_for_tighten_stop():
    allowed, reason = validate_de_risk_only(
        _trade(stop_loss_price=90.0),
        _decision("TIGHTEN_STOP", new_stop_loss_price=89.0),
    )

    assert not allowed
    assert reason == "cannot lower stop-loss for long position"


def test_validate_accepts_higher_stop_for_tighten_stop():
    allowed, reason = validate_de_risk_only(
        _trade(stop_loss_price=90.0),
        _decision("TIGHTEN_STOP", new_stop_loss_price=95.0),
    )

    assert allowed
    assert reason is None


def test_validate_rejects_higher_take_profit_for_lower_take_profit():
    allowed, reason = validate_de_risk_only(
        _trade(take_profit_price=120.0),
        _decision("LOWER_TAKE_PROFIT", new_take_profit_price=125.0),
    )

    assert not allowed
    assert reason == "cannot raise take-profit for long position"


def test_validate_accepts_lower_take_profit_for_lower_take_profit():
    allowed, reason = validate_de_risk_only(
        _trade(take_profit_price=120.0),
        _decision("LOWER_TAKE_PROFIT", new_take_profit_price=110.0),
    )

    assert allowed
    assert reason is None


def test_technical_exit_reviewer_lowers_take_profit_for_profitable_sell_signal():
    class FakeMultiEngine:
        def compute(self, _symbol):
            return _market(price=110.0)

    class FakeTechnicalAgent:
        def __init__(self, **_kwargs):
            pass

        def generate_signal(self, _snapshot):
            return AgentResponse(
                symbol="AAPL",
                signal="SELL",
                confidence=0.5,
                reasoning=["Momentum rolled over"],
                agent="technical",
            )

    reviewer = TechnicalExitReviewer(FakeMultiEngine(), technical_agent_factory=FakeTechnicalAgent)

    decision = reviewer.review(_trade(price=100.0), SimpleNamespace(symbol="AAPL"))

    assert decision.action == "LOWER_TAKE_PROFIT"
    assert decision.new_take_profit_price == 110.0


class FakeRepo:
    trades: ClassVar[list[Trade]] = []
    last: ClassVar["FakeRepo | None"] = None

    def __init__(self, _session):
        self._trades = FakeRepo.trades
        self.events = []
        FakeRepo.last = self

    def open_bracketed_trades(self):
        return self._trades

    def record_bracket_event(self, **kwargs):
        self.events.append(kwargs)

    def update_take_profit_leg(self, trade, *, order_id, price):
        trade.take_profit_order_id = order_id
        trade.take_profit_price = price

    def update_stop_loss_leg(self, trade, *, order_id, price):
        trade.stop_loss_order_id = order_id
        trade.stop_loss_price = price


class FakeAlpaca:
    def __init__(self, positions=None, available_qty=5.0):
        self.positions = positions if positions is not None else [SimpleNamespace(symbol="AAPL")]
        self.available_qty = available_qty
        self.replace_calls = []
        self.events = []
        self.sell_calls = []

    def get_positions(self):
        return self.positions

    def replace_order(self, order_id, *, limit_price=None, stop_price=None, client_order_id=None):
        self.replace_calls.append(
            {
                "order_id": order_id,
                "limit_price": limit_price,
                "stop_price": stop_price,
                "client_order_id": client_order_id,
            }
        )
        return SimpleNamespace(id=f"{order_id}-new")

    def get_available_qty(self, symbol):
        self.events.append(f"available:{symbol}")
        return self.available_qty

    def sell(self, symbol, qty):
        self.events.append(f"sell:{symbol}")
        self.sell_calls.append((symbol, qty))
        return SimpleNamespace(id="close-1")


class FakeReviewer:
    def __init__(self, decision):
        self.decision = decision

    def review(self, _trade, _position):
        return self.decision


@contextmanager
def fake_session():
    yield SimpleNamespace()


def _run_job(monkeypatch, trades, decision, alpaca=None):
    FakeRepo.trades = trades
    monkeypatch.setattr(position_review_module, "TradeRepository", FakeRepo)
    monkeypatch.setattr(position_review_module, "get_session", fake_session)
    job = PositionReviewJob(alpaca or FakeAlpaca(), FakeReviewer(decision))
    job.run()
    assert FakeRepo.last is not None
    return job, FakeRepo.last


def test_position_review_tighten_stop_replaces_stop_order(monkeypatch):
    trade = _trade(stop_loss_price=90.0)

    job, repo = _run_job(
        monkeypatch,
        [trade],
        _decision("TIGHTEN_STOP", new_stop_loss_price=96.0),
    )

    assert job.alpaca.replace_calls == [
        {
            "order_id": "sl-1",
            "limit_price": None,
            "stop_price": 96.0,
            "client_order_id": None,
        }
    ]
    assert trade.stop_loss_order_id == "sl-1-new"
    assert repo.events[0]["event_type"] == "stop_replaced"


def test_position_review_lower_take_profit_replaces_limit_order(monkeypatch):
    trade = _trade(take_profit_price=120.0)

    job, repo = _run_job(
        monkeypatch,
        [trade],
        _decision("LOWER_TAKE_PROFIT", new_take_profit_price=110.0),
    )

    assert job.alpaca.replace_calls == [
        {
            "order_id": "tp-1",
            "limit_price": 110.0,
            "stop_price": None,
            "client_order_id": None,
        }
    ]
    assert trade.take_profit_order_id == "tp-1-new"
    assert repo.events[0]["event_type"] == "take_profit_replaced"


def test_position_review_records_invalid_decision_without_alpaca_call(monkeypatch):
    trade = _trade(stop_loss_price=90.0)

    job, repo = _run_job(
        monkeypatch,
        [trade],
        _decision("TIGHTEN_STOP", new_stop_loss_price=80.0),
    )

    assert job.alpaca.replace_calls == []
    assert repo.events[0]["event_type"] == "review_rejected"


def test_position_review_records_state_mismatch_when_position_missing(monkeypatch):
    trade = _trade()
    alpaca = FakeAlpaca(positions=[])

    job, repo = _run_job(
        monkeypatch,
        [trade],
        _decision("HOLD"),
        alpaca=alpaca,
    )

    assert job.alpaca.replace_calls == []
    assert repo.events[0]["event_type"] == "state_mismatch"


def test_position_review_close_checks_available_qty_before_sell(monkeypatch):
    trade = _trade(qty=5.0)
    alpaca = FakeAlpaca(available_qty=2.0)

    job, repo = _run_job(
        monkeypatch,
        [trade],
        _decision("CLOSE"),
        alpaca=alpaca,
    )

    assert job.alpaca.events == ["available:AAPL", "sell:AAPL"]
    assert job.alpaca.sell_calls == [("AAPL", 2.0)]
    assert repo.events[0]["event_type"] == "early_close_submitted"


def test_position_review_interval_rejects_zero(monkeypatch):
    monkeypatch.setenv("POSITION_REVIEW_INTERVAL", "0")

    assert _env_int("POSITION_REVIEW_INTERVAL", 60, min_value=1) == 60
