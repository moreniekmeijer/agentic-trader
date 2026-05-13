import logging
from typing import List

from agentic_trader.scanner.models import ScanResult

logger = logging.getLogger(__name__)


class ScannerEngine:
    def __init__(self, provider, market_engine, feature_builder):
        self.provider = provider
        self.market_engine = market_engine
        self.feature_builder = feature_builder

    def scan(self, symbols: List[str], top_number: int = 3) -> List[ScanResult]:
        results = []

        for symbol in symbols:
            try:
                df = self.provider.get_bars(symbol)

                df = self.market_engine.compute(df=df)

                snapshot = self.feature_builder.build(df=df, symbol=symbol)

                rsi = snapshot.rsi
                volume = snapshot.volume
                price = snapshot.price

                score = self._score(rsi, volume)

                results.append(
                    ScanResult(
                        symbol=symbol,
                        score=score,
                        rsi=rsi,
                        volume=volume,
                        price=price,
                    )
                )

            except Exception as e:
                logger.warning(f"Scan failed for {symbol}: {e}")

        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_number]

    def _score(self, rsi, volume):
        score = 0

        # RSI extremes
        if rsi is not None:
            if rsi < 30:
                score += (30 - rsi) / 30
            elif rsi > 70:
                score += (rsi - 70) / 30

        # volume boost
        if volume is not None:
            score += min(volume / 1_000_000, 1)

        return round(score, 3)
