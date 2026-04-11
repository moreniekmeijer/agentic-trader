import pandas as pd

from agentic_trader.services.market_data.feature_builder import FeatureBuilder
from agentic_trader.services.market_data.market_data_engine import MarketDataEngine
from agentic_trader.services.market_data.providers.provider import MarketDataProvider
from agentic_trader.services.market_data.response import MultiTimeframeSnapshot


class MultiTimeframeEngine:
    def __init__(self, provider: MarketDataProvider, engine: MarketDataEngine, features: FeatureBuilder):
        self.provider = provider
        self.engine = engine
        self.features = features

    def compute(self, symbol: str) -> MultiTimeframeSnapshot:
        return self._build(
            symbol=symbol,
            df_daily=self.provider.get_bars(symbol, interval="1d"),
            df_4h=self.provider.get_bars(symbol, interval="4h"),
        )

    def compute_from_cache(
        self, symbol: str, df_daily: pd.DataFrame, df_4h: pd.DataFrame
    ) -> MultiTimeframeSnapshot:
        return self._build(symbol=symbol, df_daily=df_daily, df_4h=df_4h)

    def _build(self, symbol: str, df_daily: pd.DataFrame, df_4h: pd.DataFrame) -> MultiTimeframeSnapshot:
        daily = self.features.build(self.engine.compute(df_daily), symbol)
        h4 = self.features.build(self.engine.compute(df_4h), symbol)
        return MultiTimeframeSnapshot(symbol=symbol, daily=daily, h4=h4)
