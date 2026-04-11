from typing import Literal

from pydantic import BaseModel


class MarketDataSnapshot(BaseModel):
    symbol: str

    price: float | None

    rsi: float | None
    rsi_prev: float | None
    rsi_trend: Literal["UP", "DOWN"] | None

    rsi_cross_30: bool | None
    rsi_cross_70: bool | None

    ma_50: float | None
    trend: Literal["BULLISH", "BEARISH"] | None

    volume: float | None
    volume_avg: float | None
    volume_spike: bool | None


class MultiTimeframeSnapshot(BaseModel):
    symbol: str
    daily: MarketDataSnapshot
    h4: MarketDataSnapshot
