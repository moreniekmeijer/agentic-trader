from __future__ import annotations

import logging

from agentic_trader.agents.models import AgentResponse, AgentVote, AggregatedResponse, Signal

logger = logging.getLogger(__name__)


class DiscussionAgent:
    def __init__(self, weights: dict[str, float]):
        self.weights = weights

    def discuss(self, symbol: str, responses: list[AgentResponse]) -> AggregatedResponse:
        votes = self._build_votes(responses)

        if not votes:
            return AggregatedResponse(
                symbol=symbol,
                signal="HOLD",
                confidence=0.0,
                reasoning=["No agent votes available"],
                votes=[],
            )

        signal, confidence, reasoning = self._aggregate(votes)

        result = AggregatedResponse(
            symbol=symbol,
            signal=signal,
            confidence=round(confidence, 2),
            reasoning=reasoning,
            votes=votes,
        )

        logger.info(result.summary())
        return result

    def _build_votes(self, responses: list[AgentResponse]) -> list[AgentVote]:
        votes = []
        for response in responses:
            weight = self.weights.get(response.agent, 0.0)
            if weight == 0.0:
                logger.debug(f"Agent '{response.agent}' has no weight, skipping")
                continue
            votes.append(
                AgentVote(
                    agent=response.agent,
                    signal=response.signal,
                    confidence=response.confidence,
                    reasoning=response.reasoning,
                    weight=weight,
                )
            )
        return votes

    def _aggregate(self, votes: list[AgentVote]) -> tuple[Signal, float, list[str]]:
        total_weight = sum(v.weight for v in votes)

        buy_score = sum(v.weighted_score for v in votes if v.signal == "BUY") / total_weight

        sell_score = sum(v.weighted_score for v in votes if v.signal == "SELL") / total_weight

        reasoning = [reason for v in votes if v.signal != "HOLD" for reason in v.reasoning]

        if buy_score > sell_score and buy_score > 0:
            return "BUY", buy_score, reasoning or ["Aggregated BUY signal"]
        elif sell_score > buy_score and sell_score > 0:
            return "SELL", sell_score, reasoning or ["Aggregated SELL signal"]
        else:
            return "HOLD", 0.0, ["No consensus across agents"]
