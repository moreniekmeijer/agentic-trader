import pytest

from agentic_trader.decision.bracket_policy import BracketPolicy, round_alpaca_price
from agentic_trader.services.market_data.response import MarketDataSnapshot, MultiTimeframeSnapshot


def _market(*, price: float = 100.0, atr: float | None = None) -> MultiTimeframeSnapshot:
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
        atr=atr,
    )
    return MultiTimeframeSnapshot(symbol="AAPL", daily=daily, h4=daily)


def test_atr_risk_is_bounded_by_minimum_pct():
    levels = BracketPolicy().from_snapshot(_market(price=100.0, atr=0.1))

    assert levels.source == "atr"
    assert levels.risk_per_share == 3.0
    assert levels.take_profit_price == 106.0
    assert levels.stop_loss_price == 97.0


def test_atr_risk_is_bounded_by_maximum_pct():
    levels = BracketPolicy().from_snapshot(_market(price=100.0, atr=10.0))

    assert levels.source == "atr"
    assert levels.risk_per_share == 8.0
    assert levels.take_profit_price == 116.0
    assert levels.stop_loss_price == 92.0


def test_fallback_source_is_used_when_atr_missing():
    levels = BracketPolicy().from_snapshot(_market(price=100.0, atr=None))

    assert levels.source == "fallback_pct"
    assert levels.take_profit_price > levels.reference_price > levels.stop_loss_price
    assert levels.risk_per_share == 5.0


def test_round_alpaca_price_uses_four_decimals_for_sub_dollar_values():
    assert round_alpaca_price(0.123456) == 0.1235


def test_policy_rejects_missing_reference_price():
    with pytest.raises(ValueError, match="valid price"):
        BracketPolicy().from_snapshot(_market(price=0.0, atr=1.0))
