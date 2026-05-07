import logging
from typing import Literal

from agentic_trader.agents.agent import BaseAgent
from agentic_trader.services.market_data.response import MultiTimeframeSnapshot

logger = logging.getLogger(__name__)

Signal = Literal["BUY", "SELL", "HOLD"]


class TechnicalAgent(BaseAgent):
    def score_long_setup(self, data: MultiTimeframeSnapshot) -> tuple[float, list[str]]:
        score_buy, _score_sell, reasons_buy, _reasons_sell = self._compute_scores(data)
        return self._clamp(score_buy), reasons_buy or ["No long setup signal"]

    def _compute_scores(self, data: MultiTimeframeSnapshot):
        daily = data.daily
        h4 = data.h4

        score_buy = 0.0
        score_sell = 0.0
        reasons_buy = []
        reasons_sell = []

        # -----------------------------
        # RSI cross
        # -----------------------------
        if h4.rsi_cross_30:
            score_buy += 0.20
            reasons_buy.append("H4 RSI crossed above 30")
        if h4.rsi_trend == "UP":
            score_buy += 0.10
            reasons_buy.append("H4 RSI trending up")

        if daily.rsi_cross_30:
            score_buy += 0.15
            reasons_buy.append("Daily RSI crossed above 30")
        if daily.rsi_trend == "UP":
            score_buy += 0.08
            reasons_buy.append("Daily RSI trending up")

        if h4.rsi_cross_70:
            score_sell += 0.20
            reasons_sell.append("H4 RSI crossed below 70")
        if h4.rsi_trend == "DOWN":
            score_sell += 0.10
            reasons_sell.append("H4 RSI trending down")

        if daily.rsi_cross_70:
            score_sell += 0.15
            reasons_sell.append("Daily RSI crossed below 70")
        if daily.rsi_trend == "DOWN":
            score_sell += 0.08
            reasons_sell.append("Daily RSI trending down")

        # -----------------------------
        # RSI level
        # -----------------------------
        if daily.rsi and daily.rsi < 45 and daily.rsi_trend == "UP":
            score_buy += 0.15
            reasons_buy.append(f"Daily RSI low ({daily.rsi:.1f}) and rising")

        if daily.rsi and daily.rsi > 55 and daily.rsi_trend == "DOWN":
            score_sell += 0.15
            reasons_sell.append(f"Daily RSI high ({daily.rsi:.1f}) and falling")

        # -----------------------------
        # Moving Average trend filter
        # -----------------------------
        if daily.trend == "BULLISH":
            score_buy += 0.20
            reasons_buy.append("Daily price above MA50")
        elif daily.trend == "BEARISH":
            score_sell += 0.20
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

        return score_buy, score_sell, reasons_buy, reasons_sell
