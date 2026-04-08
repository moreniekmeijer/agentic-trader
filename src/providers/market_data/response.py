from typing import Literal

from pydantic import BaseModel


class MarketDataSnapshot(BaseModel):
    symbol: str

    price: float

    rsi: float
    rsi_prev: float
    rsi_trend: Literal["UP", "DOWN"]

    rsi_cross_30: bool
    rsi_cross_70: bool

    ma_50: float
    trend: Literal["BULLISH", "BEARISH"]

    volume: float
    volume_avg: float
    volume_spike: bool


class MultiTimeframeSnapshot(BaseModel):
    symbol: str
    daily: MarketDataSnapshot
    h4: MarketDataSnapshot
