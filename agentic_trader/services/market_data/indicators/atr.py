import pandas as pd

from agentic_trader.services.market_data.indicators.indicator import Indicator


class AverageTrueRangeIndicator(Indicator):
    def __init__(self, period: int = 14):
        self.period = period

    def compute(self, df) -> dict:
        previous_close = df["close"].shift(1)
        ranges = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - previous_close).abs(),
                (df["low"] - previous_close).abs(),
            ],
            axis=1,
        )

        true_range = ranges.max(axis=1)
        return {"atr": true_range.rolling(window=self.period).mean()}
