from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LearningQuery(BaseModel):
    symbol: str | None = None
    sector: str | None = None
    setup_type: str | None = None
    agent: str | None = None
    min_horizon_days: int | None = None
    max_horizon_days: int | None = None
    limit: int = Field(default=100, gt=0, le=500)


class AgentVoteLearningSnapshot(BaseModel):
    agent: str
    signal: str
    confidence: float
    weight: float
    reasoning: list[str] = Field(default_factory=list)


class DecisionLearningSnapshot(BaseModel):
    decision_id: int
    symbol: str
    timestamp: datetime
    action: str
    confidence: float
    reasoning: list[str] = Field(default_factory=list)
    executed: bool
    blocked_reason: str | None = None
    thesis: str | None = None
    invalidation: str | None = None
    expected_horizon_days: int | None = None
    sector: str | None = None
    setup_type: str | None = None
    evidence: list[str] = Field(default_factory=list)
    market_snapshot: dict | None = None
    votes: list[AgentVoteLearningSnapshot] = Field(default_factory=list)


class RejectedRecommendationSnapshot(DecisionLearningSnapshot):
    rejected_rule: str


class TradeOutcomeSnapshot(BaseModel):
    trade_id: int
    symbol: str
    opened_at: datetime
    closed_at: datetime
    side: str
    qty: float
    entry_price: float
    close_price: float
    realized_pnl: float
    realized_pnl_pct: float
    holding_days: int | None = None
    exit_reason: str | None = None
    max_favorable_excursion: float | None = None
    max_adverse_excursion: float | None = None
    decision: DecisionLearningSnapshot | None = None
    reflection: str | None = None
