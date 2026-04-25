import pandas as pd

from agentic_trader.services.market_data.response import MarketDataSnapshot, RsiTrend, Trend


class FeatureBuilder:
    def build(self, df: pd.DataFrame, symbol: str):
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        def safe(col):
            return float(latest[col]) if col in df.columns else None

        def safe_prev(col):
            return float(prev[col]) if col in df.columns else None

        rsi = safe("rsi")
        prev_rsi = safe_prev("rsi")
        ma_50 = safe("ma_50")
        close = safe("close")
        volume = safe("volume")
        volume_avg = safe("volume_avg")

        trend: Trend | None = None
        if ma_50 and close:
            trend: Trend = "BULLISH" if close > ma_50 else "BEARISH"

        rsi_trend: RsiTrend | None = None
        if rsi and prev_rsi:
            rsi_trend: RsiTrend = "UP" if rsi > prev_rsi else "DOWN"

        return MarketDataSnapshot(
            symbol=symbol,
            price=close,
            rsi=rsi,
            rsi_prev=prev_rsi,
            rsi_trend=rsi_trend,
            rsi_cross_30=(prev_rsi < 30 < rsi) if rsi and prev_rsi else None,
            rsi_cross_70=(prev_rsi > 70 > rsi) if rsi and prev_rsi else None,
            ma_50=ma_50,
            trend=trend,
            volume=volume,
            volume_avg=volume_avg,
            volume_spike=(volume > volume_avg) if volume and volume_avg else None,
        )
