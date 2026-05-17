from typing import Literal

from pydantic import BaseModel, Field

Signal = Literal["BUY", "SELL", "HOLD", "NEUTRAL", "REDUCE", "EXIT"]


class AgentResponse(BaseModel):
    symbol: str
    signal: Signal
    confidence: float
    reasoning: list[str]
    agent: str = "aggregated"
    entry_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    conviction: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    thesis: str | None = None
    invalidation: str | None = None
    expected_horizon_days: int | None = None
    evidence: list[str] = Field(default_factory=list)
    market_snapshot: dict | None = None


class AgentVote(BaseModel):
    agent: str
    signal: Signal
    confidence: float
    reasoning: list[str]
    weight: float

    @property
    def weighted_score(self) -> float:
        return self.confidence * self.weight


class AggregatedResponse(AgentResponse):
    votes: list[AgentVote]

    def summary(self) -> str:
        lines = [f"{v.agent}: {v.signal} ({v.confidence:.2f}) × {v.weight}" for v in self.votes]
        return f"{self.symbol} → {self.signal} ({self.confidence:.2f})\n" + "\n".join(lines)
