from datetime import datetime, timezone

from agentic_trader.services.sentiment.models import SentimentSnapshot
from agentic_trader.services.sentiment.provider import SentimentProvider


class NullSentimentProvider(SentimentProvider):
    """Neutral provider used until a real news/social sentiment source is configured."""

    def get_sentiment(self, symbol: str) -> SentimentSnapshot:
        return SentimentSnapshot(
            symbol=symbol,
            fetched_at=datetime.now(timezone.utc),
            score=0.0,
            confidence=0.0,
            reasoning=["No sentiment provider configured"],
        )
