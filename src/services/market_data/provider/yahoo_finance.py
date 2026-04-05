import yfinance as yf

from services.market_data.provider.provider import MarketDataProvider


class YahooFinanceProvider(MarketDataProvider):
    def get_bars(self, symbol: str, days: int = 200):
        period = f"{days}d"
        data = yf.download(symbol, period=period, interval="1d", progress=False)
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
