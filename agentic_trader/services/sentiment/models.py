from datetime import datetime

from pydantic import BaseModel, Field


class SentimentSnapshot(BaseModel):
    """Provider-level sentiment facts for one symbol."""

    symbol: str
    fetched_at: datetime
    score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: list[str] = Field(default_factory=list)
