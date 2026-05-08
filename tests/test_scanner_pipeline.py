from datetime import datetime, timezone
from typing import cast

import pandas as pd

import agentic_trader.worker.worker as worker_module
from agentic_trader.agents.discussion.agent import DiscussionAgent
from agentic_trader.agents.models import AgentResponse
from agentic_trader.agents.sentiment.agent import SentimentAgent
from agentic_trader.decision.engine import DecisionEngine
from agentic_trader.scanner.engine import ScannerEngine
from agentic_trader.scanner.models import CandidateContext
from agentic_trader.services.fundamentals.models import FundamentalsSnapshot
from agentic_trader.services.market_data.multi_timeframe_engine import MultiTimeframeEngine
from agentic_trader.services.market_data.response import MarketDataSnapshot, MultiTimeframeSnapshot
from agentic_trader.services.sentiment.models import SentimentSnapshot
from agentic_trader.worker.models import TimeframeData
from agentic_trader.worker.scan_state import WorkerState
from agentic_trader.worker.worker import _trade_symbol


def _fundamentals(symbol: str, growth: float) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        symbol=symbol,
        fetched_at=datetime.now(timezone.utc),
        pe_ratio=None,
        forward_pe=None,
        price_to_book=None,
        revenue_growth_yoy=growth,
        earnings_growth_yoy=None,
        profit_margin=None,
        debt_to_equity=None,
        return_on_equity=None,
        analyst_rating=None,
        price_target=None,
        sector=None,
        industry=None,
    )


def _market(symbol: str, *, long_setup: bool) -> MultiTimeframeSnapshot:
    if long_setup:
        daily = MarketDataSnapshot(
            symbol=symbol,
            price=100.0,
            rsi=40.0,
            rsi_prev=35.0,
            rsi_trend="UP",
            rsi_cross_30=True,
            rsi_cross_70=False,
            ma_50=90.0,
            trend="BULLISH",
            volume=2_000_000,
            volume_avg=1_000_000,
            volume_spike=True,
        )
        h4 = daily.model_copy(update={"rsi_cross_30": True, "volume_spike": True})
    else:
        daily = MarketDataSnapshot(
            symbol=symbol,
            price=100.0,
            rsi=72.0,
            rsi_prev=75.0,
            rsi_trend="DOWN",
            rsi_cross_30=False,
            rsi_cross_70=True,
            ma_50=110.0,
            trend="BEARISH",
            volume=900_000,
            volume_avg=1_000_000,
            volume_spike=False,
        )
        h4 = daily.model_copy(update={"rsi_cross_70": True})
    return MultiTimeframeSnapshot(symbol=symbol, daily=daily, h4=h4)


def _candidate(symbol: str, quality_score: float = 0.4) -> CandidateContext:
    return CandidateContext(
        symbol=symbol,
        stage="quality_universe",
        quality_score=quality_score,
        stage_score=quality_score,
        updated_at=datetime.now(timezone.utc),
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame([{"close": 1.0}, {"close": 2.0}])


def test_quality_universe_ranks_top_30_and_preserves_fundamentals():
    scanner = ScannerEngine(provider=None, market_engine=None, feature_builder=None)
    snapshots = {f"S{i:02d}": _fundamentals(f"S{i:02d}", growth=i / 100) for i in range(35)}

    candidates = scanner.build_quality_universe(snapshots, top_number=30)

    assert len(candidates) == 30
    assert candidates[0].symbol == "S34"
    assert candidates[-1].symbol == "S05"
    assert candidates[0].stage == "quality_universe"
    assert candidates[0].fundamentals == snapshots["S34"]
    assert candidates[0].evaluator_responses[0].agent == "fundamentals"


def test_active_shortlist_is_long_only_and_keeps_market_context():
    scanner = ScannerEngine(provider=None, market_engine=None, feature_builder=None)
    candidates = [_candidate("LONG", 0.5), _candidate("SELLISH", 0.8)]
    market = {
        "LONG": _market("LONG", long_setup=True),
        "SELLISH": _market("SELLISH", long_setup=False),
    }

    shortlist = scanner.build_active_shortlist(candidates, market, top_number=10)

    assert [candidate.symbol for candidate in shortlist] == ["LONG"]
    assert shortlist[0].stage == "active_shortlist"
    assert shortlist[0].market == market["LONG"]
    assert shortlist[0].technical_score > 0
    assert any(response.agent == "technical" for response in shortlist[0].evaluator_responses)


def test_sentiment_agent_returns_soft_agent_response():
    snapshot = SentimentSnapshot(
        symbol="AAPL",
        fetched_at=datetime.now(timezone.utc),
        score=-0.8,
        confidence=0.5,
        reasoning=["Negative news flow"],
    )

    response = SentimentAgent(symbol="AAPL", buy_threshold=0.3, sell_threshold=0.3).generate_signal(snapshot)

    assert response.agent == "sentiment"
    assert response.signal == "SELL"
    assert response.confidence == 0.4
    assert response.reasoning == ["Negative news flow"]


def test_worker_state_enriches_shortlist_without_removing_symbols():
    state = WorkerState()
    candidate = _candidate("AAPL")
    state.update_quality_universe([candidate])
    state.update_active_shortlist(
        [candidate.model_copy(update={"stage": "active_shortlist"})],
        {"AAPL": TimeframeData(daily=_frame(), h4=_frame())},
    )

    enriched = state.active_shortlist[0].model_copy(
        update={
            "stage": "sentiment_enriched",
            "sentiment_score": -0.6,
            "evaluator_responses": [
                AgentResponse(
                    symbol="AAPL",
                    signal="SELL",
                    confidence=0.6,
                    reasoning=["Soft negative input"],
                    agent="sentiment",
                )
            ],
        }
    )
    state.update_sentiment([enriched])

    assert state.symbols == ["AAPL"]
    assert state.active_shortlist[0].stage == "sentiment_enriched"
    stored = state.get_candidate("AAPL")
    assert stored is not None
    assert stored.sentiment_score == -0.6


def test_trade_symbol_consumes_candidate_votes_without_recomputing_market(monkeypatch):
    state = WorkerState()
    candidate = _candidate("AAPL").model_copy(
        update={
            "stage": "sentiment_enriched",
            "market": _market("AAPL", long_setup=True),
            "evaluator_responses": [
                AgentResponse(
                    symbol="AAPL",
                    signal="BUY",
                    confidence=0.5,
                    reasoning=["Long setup"],
                    agent="technical",
                ),
                AgentResponse(
                    symbol="AAPL",
                    signal="BUY",
                    confidence=0.4,
                    reasoning=["Quality setup"],
                    agent="fundamentals",
                ),
                AgentResponse(
                    symbol="AAPL",
                    signal="SELL",
                    confidence=0.9,
                    reasoning=["Soft negative input"],
                    agent="sentiment",
                ),
            ],
        }
    )
    state.update_active_shortlist([candidate], {"AAPL": TimeframeData(daily=_frame(), h4=_frame())})
    monkeypatch.setattr(worker_module, "state", state)

    class FailingMultiEngine:
        def compute_from_cache(self, *_args, **_kwargs):
            raise AssertionError("candidate votes should avoid market recompute")

    class CapturingDecisionEngine:
        def __init__(self):
            self.response = None
            self.bracket_levels = None

        def execute_decision(self, response, bracket_levels=None):
            self.response = response
            self.bracket_levels = bracket_levels

    decision_engine = CapturingDecisionEngine()

    _trade_symbol(
        "AAPL",
        cast(MultiTimeframeEngine, FailingMultiEngine()),
        DiscussionAgent(weights={"technical": 0.6, "fundamentals": 0.3, "sentiment": 0.1}),
        cast(DecisionEngine, decision_engine),
    )

    assert decision_engine.response is not None
    assert {vote.agent for vote in decision_engine.response.votes} == {
        "technical",
        "fundamentals",
        "sentiment",
    }
    assert decision_engine.bracket_levels is not None
