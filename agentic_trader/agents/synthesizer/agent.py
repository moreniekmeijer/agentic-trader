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

    def discuss_batch(self, symbol_reports: dict[str, list[AgentResponse]], past_lessons: dict[str, list[str]] = None) -> list[AggregatedResponse]:
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
                context_blocks.append(f"   - {v.agent.upper()}: {v.signal} (Conf: {v.confidence})\n     Reasoning: {', '.join(v.reasoning)}")
            
            lessons_str = f"\n   Past Lessons: {', '.join(lessons)}" if lessons else ""
            
            all_context.append(f"## SYMBOL: {symbol}\n{chr(10).join(context_blocks)}{lessons_str}")

        symbols_str = "\n\n".join(all_context)
        
        prompt = f"""
You are the Chief Investment Officer (CIO) of a high-performance hedge fund.
Your task is to review the following reports for several stocks and decide which ones deserve capital allocation.

CRITICAL GUIDELINES:
1. BE SKEPTICAL: Most trades are traps. Look for reasons NOT to trade.
2. COMPARATIVE ANALYSIS: If multiple stocks look good, prioritize the one with the strongest confluence of Technicals, Fundamentals, and Sentiment.
3. RISK MANAGEMENT: Do not allocate to more than 3 stocks in this batch. If none are truly exceptional, default to HOLD for everything.
4. RED FLAGS: If an analyst has a SELL signal or very low confidence, treat it as a major warning.

ANALYST REPORTS:
{symbols_str}

Provide your decisions as a JSON object where each key is a ticker symbol:
{{
  "TICKER": {{
    "signal": "BUY" | "SELL" | "HOLD",
    "confidence": float,
    "reasoning": [ "Critical reason 1", "Comparison vs others" ],
    "entry_price": float (if BUY),
    "stop_loss_price": float (if BUY),
    "take_profit_price": float (if BUY),
    "conviction": "LOW" | "MEDIUM" | "HIGH" (if BUY)
  }},
  ...
}}
"""

        try:
            logger.info(f"Arena Synthesizer invoking Groq LLM for {len(symbol_reports)} symbols...")
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a ruthless, data-driven Hedge Fund Manager. Output ONLY valid JSON."},
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
                    
                decision = SynthesizerDecision(**decision_data)
                results.append(AggregatedResponse(
                    symbol=symbol,
                    signal=decision.signal,
                    confidence=decision.confidence,
                    reasoning=decision.reasoning,
                    votes=self._build_votes(symbol_reports[symbol]),
                    entry_price=decision.entry_price,
                    stop_loss_price=decision.stop_loss_price,
                    take_profit_price=decision.take_profit_price,
                    conviction=decision.conviction,
                ))
            
            return results

        except Exception as e:
            logger.error(f"Batch LLM Synthesis failed: {e}")
            return []

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
