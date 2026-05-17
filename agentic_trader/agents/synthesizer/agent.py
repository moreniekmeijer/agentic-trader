import json
import logging
from typing import Literal

from groq import Groq
from pydantic import BaseModel, Field

from agentic_trader.agents.models import AgentResponse, AgentVote, AggregatedResponse, Signal

logger = logging.getLogger(__name__)


class SynthesizerDecision(BaseModel):
    signal: Signal
    confidence: float
    reasoning: list[str]
    entry_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    conviction: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    thesis: str | None = None
    invalidation: str | None = None
    expected_horizon_days: int | None = None
    evidence: list[str] = Field(default_factory=list)


class SynthesizerAgent:
    """
    True agentic synthesizer. Takes individual analyst responses,
    feeds them into an LLM, and uses structured outputs to form a
    deliberated trading decision.
    """

    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.client = Groq()
        self.model = model

    def discuss(
        self,
        symbol: str,
        responses: list[AgentResponse],
        past_lessons: list[str] | None = None,
    ) -> AggregatedResponse:
        decisions = self.discuss_batch({symbol: responses}, past_lessons={symbol: past_lessons or []})
        if decisions:
            return decisions[0]

        return AggregatedResponse(
            symbol=symbol,
            signal="HOLD",
            confidence=0.0,
            reasoning=["Synthesizer failed; defaulting to HOLD."],
            votes=self._build_votes(responses),
        )

    def discuss_batch(
        self, symbol_reports: dict[str, list[AgentResponse]], past_lessons: dict[str, list[str]] = None
    ) -> list[AggregatedResponse]:
        """
        Arena Mode: Review reports for MULTIPLE symbols and pick the best ones.
        """
        past_lessons = past_lessons or {}

        # Build context for all symbols
        all_context = []
        for symbol, responses in symbol_reports.items():
            votes = self._build_votes(responses)
            lessons = past_lessons.get(symbol, [])

            context_blocks = []
            for v in votes:
                reasoning = ", ".join(v.reasoning)
                context_blocks.append(
                    f"   - {v.agent.upper()}: {v.signal} (Conf: {v.confidence})\n"
                    f"     Reasoning: {reasoning}"
                )

            lessons_str = f"\n   Past Lessons: {', '.join(lessons)}" if lessons else ""

            all_context.append(f"## SYMBOL: {symbol}\n{chr(10).join(context_blocks)}{lessons_str}")

        symbols_str = "\n\n".join(all_context)

        prompt = f"""
You are the Chief Investment Officer (CIO) of a high-performance hedge fund.
Your task is to review the following reports for several stocks and decide which ones deserve capital
allocation.

CRITICAL GUIDELINES:
1. BE SKEPTICAL: Most trades are traps. Look for reasons NOT to trade.
2. COMPARATIVE ANALYSIS: If multiple stocks look good, prioritize the one with the strongest
   confluence of Technicals, Fundamentals, and Sentiment.
3. RISK MANAGEMENT: You may rank candidates, but you may NOT choose quantity, position size, or submit orders.
4. SENTIMENT IS SOFT: Sentiment may adjust confidence, but sentiment alone is never enough for BUY.
5. RED FLAGS: If an analyst has a SELL signal or very low confidence, treat it as a major warning.
6. SWING TRADING ONLY: Expected holding horizon must be between 2 and 100 days.

ANALYST REPORTS:
{symbols_str}

Provide your decisions as a JSON object where each key is a ticker symbol:
{{
  "TICKER": {{
    "signal": "BUY" | "HOLD" | "REDUCE" | "EXIT",
    "confidence": float,
    "reasoning": [ "Critical reason 1", "Comparison vs others" ],
    "entry_price": float (if BUY),
    "stop_loss_price": float (if BUY),
    "take_profit_price": float (if BUY),
    "conviction": "LOW" | "MEDIUM" | "HIGH" (if BUY),
    "thesis": "One-sentence trade thesis if BUY",
    "invalidation": "Specific condition that invalidates the thesis if BUY",
    "expected_horizon_days": integer between 2 and 100 if BUY,
    "evidence": [ "technical/fundamental/sentiment evidence used" ]
  }},
  ...
}}
"""

        try:
            logger.info(f"Arena Synthesizer invoking Groq LLM for {len(symbol_reports)} symbols...")
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a ruthless, data-driven Hedge Fund Manager. "
                            "Output ONLY valid JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            raw_response = completion.choices[0].message.content
            batch_decisions = json.loads(raw_response)

            results = []
            for symbol, decision_data in batch_decisions.items():
                if symbol not in symbol_reports:
                    continue

                decision_data["signal"] = _normalize_decision_signal(decision_data.get("signal"))
                decision_data["conviction"] = _normalize_conviction(decision_data.get("conviction"))
                decision = SynthesizerDecision(**decision_data)
                results.append(
                    AggregatedResponse(
                        symbol=symbol,
                        signal=decision.signal,
                        confidence=decision.confidence,
                        reasoning=decision.reasoning,
                        votes=self._build_votes(symbol_reports[symbol]),
                        entry_price=decision.entry_price,
                        stop_loss_price=decision.stop_loss_price,
                        take_profit_price=decision.take_profit_price,
                        conviction=decision.conviction,
                        thesis=decision.thesis,
                        invalidation=decision.invalidation,
                        expected_horizon_days=decision.expected_horizon_days,
                        evidence=decision.evidence,
                    )
                )

            return results

        except Exception as e:
            logger.error(f"Batch LLM Synthesis failed: {e}")
            return []

    def _build_votes(self, responses: list[AgentResponse]) -> list[AgentVote]:
        votes = []
        for response in responses:
            votes.append(
                AgentVote(
                    agent=response.agent,
                    signal=response.signal,
                    confidence=response.confidence,
                    reasoning=response.reasoning,
                    weight=1.0,  # Weights are implicit in the LLM's reasoning now
                )
            )
        return votes


def _normalize_decision_signal(raw: object) -> str:
    signal = str(raw or "HOLD").upper()
    if signal == "SELL":
        return "EXIT"
    if signal == "NEUTRAL":
        return "HOLD"
    if signal not in {"BUY", "HOLD", "REDUCE", "EXIT"}:
        return "HOLD"
    return signal


def _normalize_conviction(raw: object) -> str | None:
    if raw is None:
        return None
    conviction = str(raw).upper()
    if conviction not in {"LOW", "MEDIUM", "HIGH"}:
        return None
    return conviction
