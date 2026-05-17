from typing import Literal

from pydantic import BaseModel, Field

from agentic_trader.agents.models import AgentResponse

CandidateStage = Literal[
    "quality_universe",
    "technical_shortlist",
    "sentiment_enriched",
    "portfolio_ranked",
]


class ScanResult(BaseModel):
    symbol: str
    score: float
    rsi: float
    volume: float
    price: float
    stage: CandidateStage = "technical_shortlist"
    reasons: list[str] = Field(default_factory=list)
    market_snapshot: dict | None = None


class CandidateReport(BaseModel):
    """Analysis bundle kept together as a candidate moves through the pipeline."""

    symbol: str
    stage: CandidateStage
    market_snapshot: dict | None = None
    agent_responses: list[AgentResponse] = Field(default_factory=list)
