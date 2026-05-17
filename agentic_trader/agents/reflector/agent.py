import json
import logging
from typing import Optional

from groq import Groq
from pydantic import BaseModel

from agentic_trader.database.models import Decision, Trade

logger = logging.getLogger(__name__)


class ReflectionResult(BaseModel):
    lesson: str
    is_positive: bool


class ReflectorAgent:
    """
    Analyzes closed trades to extract lessons for the Synthesizer.
    """

    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.client = Groq()
        self.model = model

    def reflect(self, trade: Trade, decision: Optional[Decision]) -> str:
        if trade.closed_at is None or trade.pnl is None or trade.needs_reconciliation:
            return "Trade not yet closed or no PNL available."

        reasons_text = ""
        if decision and decision.reasoning:
            reasons_text = "\n- ".join(decision.reasoning)
        else:
            reasons_text = "No recorded reasoning."

        prompt = f"""
You are an expert post-trade analyst.
Review the following closed trade for {trade.symbol}.

Original Signal: {trade.side.upper()}
Realized PNL: {trade.pnl}
Original Reasoning:
{reasons_text}

Provide a concise, 1-2 sentence observation from this trade.
If PNL is positive, what did we do right? If negative, what did we miss?
Do not recommend code changes, automatic rule changes, or hidden strategy mutation.

Provide your response as a JSON object matching this schema:
{{
  "lesson": "string",
  "is_positive": boolean
}}
"""

        try:
            logger.info(f"Reflector generating lesson via Groq for {trade.symbol}...")
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a concise financial reflection AI. "
                            "You must ONLY output valid JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            raw_response = completion.choices[0].message.content
            result_data = json.loads(raw_response)
            result = ReflectionResult(**result_data)

            return result.lesson

        except Exception as e:
            logger.error(f"Reflector failed for {trade.symbol}: {e}")
            return f"Failed to generate reflection: {e}"
