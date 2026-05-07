import logging

from agentic_trader.services.sentiment.models import SentimentSnapshot
from agentic_trader.services.sentiment.provider import SentimentProvider

logger = logging.getLogger(__name__)


class SentimentEngine:
    def __init__(self, provider: SentimentProvider):
        self.provider = provider

    def fetch(self, symbol: str) -> SentimentSnapshot | None:
        try:
            return self.provider.get_sentiment(symbol)
        except Exception as e:
            logger.warning(f"Failed to fetch sentiment for {symbol}: {e}")
            return None

    def fetch_many(self, symbols: list[str]) -> dict[str, SentimentSnapshot]:
        result = {}
        for symbol in symbols:
            snapshot = self.fetch(symbol)
            if snapshot is not None:
                result[symbol] = snapshot
        return result
