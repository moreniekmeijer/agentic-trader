from typing import Literal

from pydantic import BaseModel

RsiTrend = Literal["UP", "DOWN"]
Trend = Literal["BULLISH", "BEARISH"]


class MarketDataSnapshot(BaseModel):
    symbol: str

    price: float | None
    rsi: float | None
    rsi_prev: float | None
    rsi_trend: RsiTrend | None

    rsi_cross_30: bool | None
    rsi_cross_70: bool | None

    ma_50: float | None
    trend: Trend | None

    volume: float | None
    volume_avg: float | None
    volume_spike: bool | None
    atr: float | None = None


class MultiTimeframeSnapshot(BaseModel):
    symbol: str
    daily: MarketDataSnapshot
    h4: MarketDataSnapshot
