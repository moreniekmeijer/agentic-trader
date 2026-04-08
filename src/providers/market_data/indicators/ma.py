from providers.market_data.indicators.indicator import Indicator


class MovingAverageIndicator(Indicator):
    def __init__(self, period=50):
        self.period = period

    def compute(self, df) -> dict:
        return {f"ma_{self.period}": df["close"].rolling(self.period).mean()}
