from abc import ABC, abstractmethod
from typing import Literal

from agentic_trader.agents.models import AgentResponse

Signal = Literal["BUY", "SELL", "HOLD"]


class BaseAgent(ABC):
    def __init__(
        self,
        symbol: str,
        buy_threshold: float,
        sell_threshold: float,
        bias: float = 0.0,
    ):
        self.symbol = symbol
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.bias = max(-1.0, min(1.0, bias))

    @abstractmethod
    def _compute_scores(self, data):
        """
        Must return:
        - score_buy: float
        - score_sell: float
        - reasons_buy: list[str]
        - reasons_sell: list[str]
        """
        raise NotImplementedError

    def _apply_bias(self, score_buy: float, score_sell: float):
        if self.bias != 0.0:
            score_buy = max(0.0, score_buy + self.bias * 0.2)
            score_sell = max(0.0, score_sell - self.bias * 0.2)

        return score_buy, score_sell

    def _decide(
        self,
        score_buy: float,
        score_sell: float,
        reasons_buy: list[str],
        reasons_sell: list[str],
    ):
        if score_buy >= self.buy_threshold and score_buy > score_sell:
            return "BUY", score_buy, reasons_buy

        if score_sell >= self.sell_threshold and score_sell > score_buy:
            return "SELL", score_sell, reasons_sell

        return "HOLD", 0.0, ["No strong signal"]

    def _clamp(self, score: float) -> float:
        return min(max(score, 0.0), 1.0)

    def _build_response(
        self,
        signal: Signal,
        confidence: float,
        reasons: list[str],
    ) -> AgentResponse:
        return AgentResponse(
            symbol=self.symbol,
            signal=signal,
            confidence=round(confidence, 2),
            reasoning=reasons,
            agent=self.__class__.__name__.replace("Agent", "").lower(),
        )

    def generate_signal(self, data) -> AgentResponse:
        score_buy, score_sell, reasons_buy, reasons_sell = self._compute_scores(data)

        score_buy, score_sell = self._apply_bias(score_buy, score_sell)

        score_buy = self._clamp(score_buy)
        score_sell = self._clamp(score_sell)

        signal, confidence, reasons = self._decide(
            score_buy, score_sell, reasons_buy, reasons_sell
        )

        return self._build_response(signal, confidence, reasons)