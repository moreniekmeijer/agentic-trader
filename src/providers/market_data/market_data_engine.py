from providers.market_data.response import MarketDataSnapshot


class MarketDataEngine:
    def __init__(self, indicators: list):
        self.indicators = indicators

    def compute(self, df, symbol: str) -> MarketDataSnapshot:
        df = df.copy()

        if len(df) < 2:
            raise ValueError("Not enough data to compute temporal features")

        for indicator in self.indicators:
            result = indicator.compute(df)
            for k, v in result.items():
                df[k] = v

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        latest_rsi = latest["rsi"].values[0]
        prev_rsi = prev["rsi"].values[0]

        latest_close = latest["close"].values[0]
        ma_50 = latest["ma_50"].values[0]
        volume = latest["volume"].values[0]
        volume_avg = latest["volume_avg"].values[0]

        rsi_trend = "UP" if latest_rsi > prev_rsi else "DOWN"
        rsi_cross_30 = prev_rsi < 30 < latest_rsi
        rsi_cross_70 = prev_rsi > 70 > latest_rsi
        trend = "BULLISH" if latest_close > ma_50 else "BEARISH"
        volume_spike = volume > volume_avg

        return MarketDataSnapshot(
            symbol=symbol,
            price=latest_close,
            rsi=latest_rsi,
            rsi_prev=prev_rsi,
            rsi_trend=rsi_trend,
            rsi_cross_30=rsi_cross_30,
            rsi_cross_70=rsi_cross_70,
            ma_50=ma_50,
            trend=trend,
            volume=volume,
            volume_avg=volume_avg,
            volume_spike=volume_spike,
        )
