from agents.technical.models import TechnicalAgentResponse
from providers.market_data.response import MultiTimeframeSnapshot


class TechnicalAgent:
    def __init__(self, symbol: str, buy_threshold: float = 0.5, sell_threshold: float = 0.5):
        self.symbol = symbol
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def generate_signal(self, data: MultiTimeframeSnapshot) -> TechnicalAgentResponse:
        daily = data.daily
        h4 = data.h4

        score_buy = 0.0
        score_sell = 0.0
        reasons_buy = []
        reasons_sell = []

        # -----------------------------
        # RSI signals
        # -----------------------------
        if h4.rsi_cross_30 and h4.rsi_trend == "UP":
            score_buy += 0.3
            reasons_buy.append("H4 RSI oversold recovery")
        if daily.rsi_cross_30 and daily.rsi_trend == "UP":
            score_buy += 0.2
            reasons_buy.append("Daily RSI oversold recovery")

        if h4.rsi_cross_70 and h4.rsi_trend == "DOWN":
            score_sell += 0.3
            reasons_sell.append("H4 RSI overbought drop")
        if daily.rsi_cross_70 and daily.rsi_trend == "DOWN":
            score_sell += 0.2
            reasons_sell.append("Daily RSI overbought drop")

        # -----------------------------
        # Moving Average trend filter
        # -----------------------------
        if daily.trend == "BULLISH":
            score_buy += 0.1
            reasons_buy.append("Daily price above MA50")
        elif daily.trend == "BEARISH":
            score_sell += 0.1
            reasons_sell.append("Daily price below MA50")

        # -----------------------------
        # Volume confirmation
        # -----------------------------
        if daily.volume_spike:
            score_buy += 0.1
            score_sell += 0.05
            reasons_buy.append("Daily volume spike")
            reasons_sell.append("Daily volume spike")
        if h4.volume_spike:
            score_buy += 0.05
            score_sell += 0.02
            reasons_buy.append("H4 volume spike")
            reasons_sell.append("H4 volume spike")

        # -----------------------------
        # Weigh signals
        # -----------------------------
        if score_buy >= self.buy_threshold and score_buy > score_sell:
            signal = "BUY"
            confidence = min(score_buy, 1.0)
            reasoning = reasons_buy
        elif score_sell >= self.sell_threshold and score_sell > score_buy:
            signal = "SELL"
            confidence = min(score_sell, 1.0)
            reasoning = reasons_sell
        else:
            signal = "HOLD"
            confidence = 0.0
            reasoning = ["No strong BUY/SELL signals"]

        return TechnicalAgentResponse(
            symbol=self.symbol,
            signal=signal,
            confidence=round(confidence, 2),
            reasoning=reasoning,
        )
