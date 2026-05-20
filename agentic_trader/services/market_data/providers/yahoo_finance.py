import pandas as pd
import yfinance
from datetime import datetime, timedelta

from agentic_trader.services.market_data.provider import MarketDataProvider

_CACHE: dict[tuple[str, int, str], tuple[datetime, pd.DataFrame]] = {}
_CACHE_TTL = timedelta(minutes=15)


class YahooFinanceProvider(MarketDataProvider):
    def get_bars(self, symbol: str, days: int = 200, interval: str = "1d") -> pd.DataFrame:
        cache_key = (symbol, days, interval)
        now = datetime.now()
        
        if cache_key in _CACHE:
            cached_time, cached_df = _CACHE[cache_key]
            if now - cached_time < _CACHE_TTL:
                return cached_df.copy()

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
        
        _CACHE[cache_key] = (now, data)
        return data.copy()
