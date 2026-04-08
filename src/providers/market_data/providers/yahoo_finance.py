import yfinance as yf

from providers.market_data.providers.provider import MarketDataProvider


class YahooFinanceProvider(MarketDataProvider):
    def get_bars(self, symbol: str, days: int = 200, interval: str = "1d"):
        period = f"{days}d"
        data = yf.download(symbol, period=period, interval=interval, progress=False)
        data = data.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        data.index.name = "timestamp"
        return data
