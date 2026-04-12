import os

from alpaca.data.historical import StockHistoricalDataClient

from agentic_trader.services.market_data.provider import MarketDataProvider


class AlpacaProvider(MarketDataProvider):
    def __init__(self):
        self.client = StockHistoricalDataClient(
            api_key=os.getenv("ALPACA_API_KEY"), secret_key=os.getenv("ALPACA_SECRET_KEY")
        )

    # def get_bars(self, symbol: str, days: int = 30):
    #     end = datetime.now()
    #     start = end - timedelta(days=days)
    #
    #     request = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=start, end=end)
    #
    #     bars = self.client.get_stock_bars(request)
    #
    #     return bars[symbol]
