import logging

from agentic_trader.services.fundamentals.models import FundamentalsSnapshot
from agentic_trader.services.fundamentals.provider import FundamentalsProvider

logger = logging.getLogger(__name__)


class FundamentalsEngine:
    def __init__(self, provider: FundamentalsProvider):
        self.provider = provider

    def fetch(self, symbol: str) -> FundamentalsSnapshot | None:
        try:
            snapshot = self.provider.get_fundamentals(symbol)
            logger.debug(
                f"{symbol} | pe={snapshot.pe_ratio} "
                f"margin={snapshot.profit_margin} "
                f"rating={snapshot.analyst_rating}"
            )
            return snapshot
        except Exception as e:
            logger.warning(f"Failed to fetch fundamentals for {symbol}: {e}")
            return None

    def fetch_many(self, symbols: list[str]) -> dict[str, FundamentalsSnapshot]:
        result = {}
        for symbol in symbols:
            snapshot = self.fetch(symbol)
            if snapshot is not None:
                result[symbol] = snapshot
        return result
