from providers.market_data.response import MultiTimeframeSnapshot


class MultiTimeframeEngine:
    def __init__(self, provider, indicator_engine):
        self.provider = provider
        self.engine = indicator_engine

    def compute(self, symbol: str) -> MultiTimeframeSnapshot:
        df_daily = self.provider.get_bars(symbol, interval="1d")
        df_4h = self.provider.get_bars(symbol, interval="4h")

        daily = self.engine.compute(df_daily, symbol)
        h4 = self.engine.compute(df_4h, symbol)

        return MultiTimeframeSnapshot(symbol=symbol, daily=daily, h4=h4)
