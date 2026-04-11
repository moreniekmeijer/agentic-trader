from typing import Literal

from pydantic import BaseModel, Field


class TechnicalAgentResponse(BaseModel):
    symbol: str
    signal: Literal["BUY", "SELL", "HOLD"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: list[str] = [
        "No strong BUY/SELL signals",
    ]
