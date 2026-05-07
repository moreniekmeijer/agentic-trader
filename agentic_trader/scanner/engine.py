import logging
from datetime import datetime, timezone
from typing import List

from agentic_trader.agents.fundamental.agent import FundamentalsAgent
from agentic_trader.agents.technical.agent import TechnicalAgent
from agentic_trader.scanner.models import CandidateContext, ScanResult
from agentic_trader.services.fundamentals.models import FundamentalsSnapshot
from agentic_trader.services.market_data.response import MultiTimeframeSnapshot

logger = logging.getLogger(__name__)


class ScannerEngine:
    def __init__(self, provider, market_engine, feature_builder):
        self.provider = provider
        self.market_engine = market_engine
        self.feature_builder = feature_builder

    def scan(self, symbols: List[str], top_number: int = 10) -> List[ScanResult]:
        results = []

        for symbol in symbols:
            try:
                df = self.provider.get_bars(symbol)

                df = self.market_engine.compute(df=df)

                snapshot = self.feature_builder.build(df=df, symbol=symbol)

                rsi = snapshot.rsi
                volume = snapshot.volume
                price = snapshot.price

                score = self._score(rsi, volume)

                results.append(
                    ScanResult(
                        symbol=symbol,
                        score=score,
                        rsi=rsi,
                        volume=volume,
                        price=price,
                    )
                )

            except Exception as e:
                logger.warning(f"Scan failed for {symbol}: {e}")

        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_number]

    def _score(self, rsi, volume):
        score = 0

        # Legacy single-stage scans stay long-only; overbought names no longer
        # receive the same boost as oversold recovery setups.
        if rsi is not None:
            if rsi < 30:
                score += (30 - rsi) / 30

        # volume boost
        if volume is not None:
            score += min(volume / 1_000_000, 1)

        return round(score, 3)

    def build_quality_universe(
        self,
        fundamentals: dict[str, FundamentalsSnapshot],
        top_number: int = 30,
    ) -> list[CandidateContext]:
        candidates: list[CandidateContext] = []

        for symbol, snapshot in fundamentals.items():
            agent = FundamentalsAgent(symbol=symbol, buy_threshold=0.3, sell_threshold=0.3)
            score, reasons = agent.score_quality(snapshot)
            response = agent.generate_signal(snapshot)
            candidates.append(
                CandidateContext(
                    symbol=symbol,
                    stage="quality_universe",
                    quality_score=score,
                    stage_score=score,
                    fundamentals=snapshot,
                    evaluator_responses=[response],
                    reasons=reasons,
                    updated_at=datetime.now(timezone.utc),
                )
            )

        candidates.sort(key=lambda candidate: candidate.quality_score, reverse=True)
        return candidates[:top_number]

    def build_active_shortlist(
        self,
        candidates: list[CandidateContext],
        market_snapshots: dict[str, MultiTimeframeSnapshot],
        top_number: int = 10,
    ) -> list[CandidateContext]:
        shortlist: list[CandidateContext] = []

        for candidate in candidates:
            market = market_snapshots.get(candidate.symbol)
            if market is None:
                continue

            agent = TechnicalAgent(symbol=candidate.symbol, buy_threshold=0.3, sell_threshold=0.3)
            score, reasons = agent.score_long_setup(market)
            if score <= 0:
                continue

            response = agent.generate_signal(market)
            shortlist.append(
                candidate.model_copy(
                    update={
                        "stage": "active_shortlist",
                        "technical_score": score,
                        "stage_score": round(candidate.quality_score + score, 3),
                        "market": market,
                        "evaluator_responses": [*candidate.evaluator_responses, response],
                        "reasons": [*candidate.reasons, *reasons],
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
            )

        shortlist.sort(key=lambda candidate: candidate.stage_score, reverse=True)
        return shortlist[:top_number]
