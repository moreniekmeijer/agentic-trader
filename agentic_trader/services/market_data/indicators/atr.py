import pandas as pd

from agentic_trader.services.market_data.indicators.indicator import Indicator


class ATRIndicator(Indicator):
    def __init__(self, period: int = 14):
        self.period = period

    def compute(self, df: pd.DataFrame) -> dict:
        self._validate_columns(df)
        atr = self._compute_atr(df)
        return {"atr": atr}

    def _compute_atr(self, df: pd.DataFrame) -> pd.Series:
        # Calculate True Range
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # Calculate ATR (Wilder's Smoothing is basically an EMA with alpha=1/period)
        # Using simple rolling mean for basic ATR, or Wilder's EMA:
        atr = tr.ewm(alpha=1 / self.period, adjust=False).mean()

        return atr

    def _validate_columns(self, df: pd.DataFrame) -> None:
        missing = {"high", "low", "close"} - set(df.columns)
        if missing:
            missing_cols = ", ".join(sorted(missing))
            raise ValueError(f"ATR requires columns: {missing_cols}")
