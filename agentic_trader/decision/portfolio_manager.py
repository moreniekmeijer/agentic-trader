from __future__ import annotations

from collections.abc import Sequence

from agentic_trader.agents.models import AgentVote, AggregatedResponse


class PortfolioManager:
    """Deterministic guardrail for LLM portfolio recommendations."""

    def validate(
        self,
        response: AggregatedResponse,
    ) -> AggregatedResponse:
        signal = self._normalize_signal(response.signal)
        reasons = list(response.reasoning)

        if signal == "BUY":
            blocked_reason = self._buy_block_reason(response)
            if blocked_reason:
                signal = "HOLD"
                reasons.append(blocked_reason)

        return response.model_copy(update={"signal": signal, "reasoning": reasons})

    def _buy_block_reason(
        self,
        response: AggregatedResponse,
    ) -> str | None:
        if not self._has_non_sentiment_buy(response.votes):
            return "BUY rejected because sentiment alone cannot justify a new position."

        if self._has_hard_non_sentiment_sell(response.votes):
            return "BUY rejected because technical or fundamental evidence contradicts it."

        if not response.thesis:
            return "BUY rejected because no thesis was provided."

        if not response.invalidation:
            return "BUY rejected because no invalidation condition was provided."

        if not response.expected_horizon_days or not 2 <= response.expected_horizon_days <= 100:
            return "BUY rejected because expected holding horizon is outside 2-100 days."

        if self._is_overbought_spike(response) and not (
            self._daily_trend_is_bullish(response) and self._has_fundamental_buy(response.votes)
        ):
            return "BUY rejected because overbought technicals lack fundamental confirmation."

        return None

    def _normalize_signal(self, signal: str) -> str:
        normalized = signal.upper()
        if normalized == "SELL":
            return "EXIT"
        if normalized == "NEUTRAL":
            return "HOLD"
        return normalized

    def _has_non_sentiment_buy(self, votes: Sequence[AgentVote]) -> bool:
        return any(
            vote.signal == "BUY" and vote.agent.lower() != "sentiment" and vote.confidence >= 0.3
            for vote in votes
        )

    def _has_fundamental_buy(self, votes: Sequence[AgentVote]) -> bool:
        return any(
            vote.signal == "BUY" and vote.agent.lower() in {"fundamental", "fundamentals"}
            for vote in votes
        )

    def _has_hard_non_sentiment_sell(self, votes: Sequence[AgentVote]) -> bool:
        return any(
            vote.signal == "SELL" and vote.agent.lower() != "sentiment" and vote.confidence >= 0.5
            for vote in votes
        )

    def _is_overbought_spike(self, response: AggregatedResponse) -> bool:
        snapshot = response.market_snapshot or {}
        h4 = snapshot.get("h4") or {}
        h4_rsi = h4.get("rsi")

        return h4_rsi is not None and h4_rsi > 70

    def _daily_trend_is_bullish(self, response: AggregatedResponse) -> bool:
        snapshot = response.market_snapshot or {}
        daily = snapshot.get("daily") or {}

        return daily.get("trend") == "BULLISH"
