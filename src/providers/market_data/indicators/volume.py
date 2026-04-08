from providers.market_data.indicators.indicator import Indicator


class VolumeIndicator(Indicator):
    def compute(self, df) -> dict:
        return {"volume_avg": df["volume"].rolling(20).mean()}
