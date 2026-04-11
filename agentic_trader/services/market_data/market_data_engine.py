class MarketDataEngine:
    def __init__(self, indicators: list):
        self.indicators = indicators

    def compute(self, df):
        df = df.copy()

        for indicator in self.indicators:
            result = indicator.compute(df)
            for k, v in result.items():
                df[k] = v

        return df
