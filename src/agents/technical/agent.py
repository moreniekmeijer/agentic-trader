from agents.technical.models import TechnicalAgentResponse
from services.market_data.helpers import get_latest_rsi


class TechnicalAgent:
    def __init__(self, symbol: str):
        self.symbol = symbol

    def generate_signal(self, df) -> TechnicalAgentResponse:
        latest_rsi = get_latest_rsi(df)

        if latest_rsi < 30:
            signal = "BUY"
            confidence = (30 - latest_rsi) / 30
            reasoning = f"RSI oversold: {latest_rsi:.1f}"
        elif latest_rsi > 70:
            signal = "SELL"
            confidence = (latest_rsi - 70) / 30
            reasoning = f"RSI overbought: {latest_rsi:.1f}"
        else:
            signal = "HOLD"
            confidence = 0.0
            reasoning = f"RSI neutral: {latest_rsi:.1f}"

        return TechnicalAgentResponse(
            symbol=self.symbol,
            signal=signal,
            confidence=round(confidence, 2),
            reasoning=reasoning
        )
