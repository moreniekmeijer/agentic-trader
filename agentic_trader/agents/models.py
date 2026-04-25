from typing import Literal

from pydantic import BaseModel

Signal = Literal["BUY", "SELL", "HOLD"]


class AgentResponse(BaseModel):
    symbol: str
    signal: Signal
    confidence: float
    reasoning: list[str]
    agent: str = "aggregated"


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
