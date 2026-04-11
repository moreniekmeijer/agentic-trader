from agentic_trader.services.market_data.indicators.indicator import Indicator


class RSIIndicator(Indicator):
    def __init__(self, period: int = 14, method: str = "ema"):
        self.period = period
        self.method = method

    def compute(self, df) -> dict:
        if self.method == "ema":
            rsi = self._compute_rsi_ema(df)
        else:
            rsi = self._compute_rsi_sma(df)

        return {"rsi": rsi}

    def _compute_rsi_ema(self, df) -> float:
        delta = df["close"].diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(span=self.period, adjust=False).mean()
        avg_loss = loss.ewm(span=self.period, adjust=False).mean()

        avg_loss = avg_loss.replace(0, 1e-10)

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _compute_rsi_sma(self, df) -> float:
        delta = df["close"].diff()

        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()

        loss = loss.replace(0, 1e-10)

        rs = gain / loss
        return 100 - (100 / (1 + rs))
