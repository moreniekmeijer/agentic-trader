from abc import ABC, abstractmethod

from agentic_trader.services.sentiment.models import SentimentSnapshot


class SentimentProvider(ABC):
    @abstractmethod
    def get_sentiment(self, symbol: str) -> SentimentSnapshot:
        raise NotImplementedError
