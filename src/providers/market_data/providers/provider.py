from abc import ABC, abstractmethod


class MarketDataProvider(ABC):
    @abstractmethod
    def get_bars(self, symbol: str, days: int):
        pass
