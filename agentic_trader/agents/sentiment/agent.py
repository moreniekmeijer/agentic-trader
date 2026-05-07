from agentic_trader.agents.agent import BaseAgent
from agentic_trader.services.sentiment.models import SentimentSnapshot


class SentimentAgent(BaseAgent):
    """Turns provider sentiment facts into a soft discussion vote."""

    def _compute_scores(self, data: SentimentSnapshot):
        score = max(-1.0, min(1.0, data.score))
        confidence = max(0.0, min(1.0, data.confidence))
        reasons = data.reasoning or ["No sentiment reasoning available"]

        if score > 0:
            return score * confidence, 0.0, reasons, []

        if score < 0:
            return 0.0, abs(score) * confidence, [], reasons

        return 0.0, 0.0, [], reasons
