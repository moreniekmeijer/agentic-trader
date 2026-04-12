from typing import Literal

from pydantic import BaseModel, Field

Signal = Literal["BUY", "SELL", "HOLD"]


class AgentResponse(BaseModel):
    symbol: str
    signal: Signal
    confidence: float
    reasoning: list[str]
    agent: str = "aggregated"