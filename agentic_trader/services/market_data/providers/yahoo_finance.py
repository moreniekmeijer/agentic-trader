import pandas as pd
import yfinance

from agentic_trader.services.market_data.provider import MarketDataProvider


class YahooFinanceProvider(MarketDataProvider):
    def get_bars(self, symbol: str, days: int = 200, interval: str = "1d") -> pd.DataFrame:
        period = f"{days}d"
        data = yfinance.download(
            symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )

        # yfinance returns a MultiIndex (Price, Ticker) when auto_adjust=True
        # Flatten to single-level columns for a single symbol
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

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
