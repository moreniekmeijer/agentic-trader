from abc import ABC, abstractmethod

from agentic_trader.services.fundamentals.models import FundamentalsSnapshot


class FundamentalsProvider(ABC):
    @abstractmethod
    def get_fundamentals(self, symbol: str) -> FundamentalsSnapshot:
        raise NotImplementedError