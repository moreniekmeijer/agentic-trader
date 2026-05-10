import json
import logging
from typing import Literal

from groq import Groq
from pydantic import BaseModel

from agentic_trader.agents.models import AgentResponse, AgentVote, AggregatedResponse

logger = logging.getLogger(__name__)

class SynthesizerDecision(BaseModel):
    signal: Literal["BUY", "SELL", "HOLD"]
    confidence: float
    reasoning: list[str]
    entry_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    conviction: Literal["LOW", "MEDIUM", "HIGH"] | None = None


class SynthesizerAgent:
    """
    True agentic synthesizer. Takes individual analyst responses,
    feeds them into an LLM, and uses structured outputs to form a 
    deliberated trading decision.
    """
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.client = Groq()
        self.model = model

    def discuss(self, symbol: str, responses: list[AgentResponse], past_lessons: list[str] = None) -> AggregatedResponse:
        past_lessons = past_lessons or []
        votes = self._build_votes(responses)

        if not votes:
            return AggregatedResponse(
                symbol=symbol,
                signal="HOLD",
                confidence=0.0,
                reasoning=["No agent votes available"],
                votes=[],
            )

        context_blocks = []
        for v in votes:
            context_blocks.append(f"### {v.agent.upper()} ANALYST ###\nSignal: {v.signal}\nConfidence: {v.confidence}\nReasoning:\n- " + "\n- ".join(v.reasoning))

        context_str = "\n\n".join(context_blocks)

        lessons_str = ""
        if past_lessons:
            lessons_str = "\n\nPast Lessons for this Symbol:\n- " + "\n- ".join(past_lessons)
            
        prompt = f"""
You are the Lead Portfolio Manager for an algorithmic trading fund.
Your task is to review the reports from your specialized analysts for the ticker symbol {symbol} 
and make a final trading decision.

Here are the reports from your analysts:
{context_str}{lessons_str}

Evaluate the conflicting or supporting evidence.
- If there's no strong signal, default to HOLD.
- Ensure you apply any Past Lessons provided to avoid repeating mistakes.
- If you signal BUY, you MUST calculate a bracket order. Set an `entry_price` Limit near the current price. 
- Use the Daily ATR (Volatility) from the Technical Thesis to set your targets. For example: `stop_loss_price` = entry - (1.5 * ATR), and `take_profit_price` = entry + (3 * ATR).
- If you signal BUY, you MUST provide a `conviction` level (LOW, MEDIUM, HIGH) which the Risk Engine will use to size the position.

Provide your final decision as a JSON object matching this schema:
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": float (between 0.0 and 1.0),
  "reasoning": [ "reason 1", "reason 2" ],
  "entry_price": float (only if BUY),
  "stop_loss_price": float (only if BUY),
  "take_profit_price": float (only if BUY),
  "conviction": "LOW" | "MEDIUM" | "HIGH" (only if BUY)
}}
"""

        try:
            logger.info(f"Synthesizer invoking Groq LLM for {symbol}...")
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a logical, risk-aware trading AI. You must ONLY output valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            raw_response = completion.choices[0].message.content
            
            # Parse the JSON string manually into our Pydantic model
            decision_data = json.loads(raw_response)
            decision = SynthesizerDecision(**decision_data)
            
            result = AggregatedResponse(
                symbol=symbol,
                signal=decision.signal,
                confidence=decision.confidence,
                reasoning=decision.reasoning,
                votes=votes,
                entry_price=decision.entry_price,
                stop_loss_price=decision.stop_loss_price,
                take_profit_price=decision.take_profit_price,
                conviction=decision.conviction,
            )
            logger.info(result.summary())
            return result

        except Exception as e:
            logger.error(f"LLM Synthesis failed for {symbol}: {e}")
            # Fallback to simple logic or HOLD
            return AggregatedResponse(
                symbol=symbol,
                signal="HOLD",
                confidence=0.0,
                reasoning=[f"LLM Error: {str(e)}"],
                votes=votes,
            )

    def _build_votes(self, responses: list[AgentResponse]) -> list[AgentVote]:
        votes = []
        for response in responses:
            votes.append(
                AgentVote(
                    agent=response.agent,
                    signal=response.signal,
                    confidence=response.confidence,
                    reasoning=response.reasoning,
                    weight=1.0, # Weights are implicit in the LLM's reasoning now
                )
            )
        return votes
