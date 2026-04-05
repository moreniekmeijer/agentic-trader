from pydantic import BaseModel, Field
from typing import Literal


class TechnicalAgentResponse(BaseModel):
    symbol: str
    signal: Literal["BUY", "SELL", "HOLD"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str