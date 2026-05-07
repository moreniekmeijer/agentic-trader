from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from agentic_trader.agents.models import AgentResponse
from agentic_trader.services.fundamentals.models import FundamentalsSnapshot
from agentic_trader.services.market_data.response import MultiTimeframeSnapshot

ScannerStage = Literal["quality_universe", "active_shortlist", "sentiment_enriched"]


class ScanResult(BaseModel):
    symbol: str
    score: float
    rsi: float
    volume: float
    price: float


class CandidateContext(BaseModel):
    """Enriched scanner output carried into downstream decisioning."""

    symbol: str
    stage: ScannerStage
    quality_score: float = 0.0
    technical_score: float = 0.0
    sentiment_score: float | None = None
    stage_score: float = 0.0
    fundamentals: FundamentalsSnapshot | None = None
    market: MultiTimeframeSnapshot | None = None
    evaluator_responses: list[AgentResponse] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    updated_at: datetime


class ScannerStageSnapshot(BaseModel):
    """Immutable view of one scanner stage's latest candidates."""

    stage: ScannerStage
    candidates: list[CandidateContext]
    timestamp: datetime

    @property
    def symbols(self) -> list[str]:
        return [candidate.symbol for candidate in self.candidates]
