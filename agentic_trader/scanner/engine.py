import logging

from agentic_trader.scanner.models import ScanResult
from agentic_trader.services.market_data.response import MarketDataSnapshot

logger = logging.getLogger(__name__)


class ScannerEngine:
    def __init__(self, provider, market_engine, feature_builder):
        self.provider = provider
        self.market_engine = market_engine
        self.feature_builder = feature_builder

    def scan(self, symbols: list[str], top_number: int = 3) -> list[ScanResult]:
        results = []

        for symbol in symbols:
            try:
                df = self.provider.get_bars(symbol)

                df = self.market_engine.compute(df=df)

                snapshot = self.feature_builder.build(df=df, symbol=symbol)

                if not self._passes_quality_universe(snapshot):
                    continue

                score, reasons = self._score(snapshot)

                results.append(
                    ScanResult(
                        symbol=symbol,
                        score=score,
                        rsi=snapshot.rsi or 0.0,
                        volume=snapshot.volume or 0.0,
                        price=snapshot.price or 0.0,
                        reasons=reasons,
                        market_snapshot=snapshot.model_dump(mode="json"),
                    )
                )

            except Exception as e:
                logger.warning(f"Scan failed for {symbol}: {e}")

        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_number]

    def _passes_quality_universe(self, snapshot: MarketDataSnapshot) -> bool:
        if snapshot.price is None or snapshot.price <= 5:
            return False
        if snapshot.volume is None or snapshot.volume < 100_000:
            return False

        return True

    def _score(self, snapshot: MarketDataSnapshot) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

        if snapshot.trend == "BULLISH":
            score += 0.40
            reasons.append("daily trend is bullish")

        if snapshot.rsi is not None:
            if 35 <= snapshot.rsi <= 65:
                score += 0.25
                reasons.append("RSI is in a swing-trading range")
            elif snapshot.rsi < 35 and snapshot.rsi_trend == "UP":
                score += 0.20
                reasons.append("RSI is recovering from oversold")
            elif snapshot.rsi > 70:
                score -= 0.35
                reasons.append("overbought spike; requires later confirmation")

        if snapshot.volume_spike:
            score += 0.20
            reasons.append("volume is above recent average")

        if snapshot.atr is not None and snapshot.price:
            atr_pct = snapshot.atr / snapshot.price
            if 0.01 <= atr_pct <= 0.08:
                score += 0.15
                reasons.append("ATR is usable for swing bracket sizing")

        return round(max(0.0, score), 3), reasons
