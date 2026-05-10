import json
import logging
from typing import Literal

from groq import Groq
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class PortfolioDecision(BaseModel):
    action: Literal["HOLD", "CLOSE_EARLY"]
    reasoning: list[str]


class PortfolioAgent:
    """
    Evaluates open positions to determine if they should be held or closed early.
    """
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.client = Groq()
        self.model = model

    def review_position(self, symbol: str, current_price: float, unrealized_pnl_pct: float, atr: float | None, original_thesis: list[str]) -> PortfolioDecision:
        thesis_str = "\n- ".join(original_thesis) if original_thesis else "No original thesis provided."
        atr_str = f"{atr:.2f}" if atr is not None else "Unknown"
        
        prompt = f"""
You are the Lead Portfolio Manager for an algorithmic trading fund.
Your task is to review the currently OPEN position for {symbol} and decide whether to HOLD or CLOSE_EARLY.

### Position Status
- Symbol: {symbol}
- Current Price: {current_price:.2f}
- Unrealized PnL: {unrealized_pnl_pct:.2%}
- Daily ATR (Volatility): {atr_str}

### Original Thesis for Buying
- {thesis_str}

### Instructions
1. We already have an automated Bracket Order (Stop Loss / Take Profit) active at the broker. 
2. Your ONLY job is to decide if the fundamental or technical thesis has invalidated *before* the automated stops are hit.
3. If the original thesis still holds, or if the trade just needs more time to play out, you MUST choose HOLD.
4. If you believe the market conditions have fundamentally changed against us, or if the risk is now unacceptable, you may choose CLOSE_EARLY to manually exit the position now.

Provide your final decision as a JSON object matching this schema:
{{
  "action": "HOLD" | "CLOSE_EARLY",
  "reasoning": [ "reason 1", "reason 2" ]
}}
"""

        try:
            logger.info(f"PortfolioAgent invoking Groq LLM to review {symbol}...")
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a logical, risk-aware portfolio manager AI. You must ONLY output valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            raw_response = completion.choices[0].message.content
            
            decision_data = json.loads(raw_response)
            decision = PortfolioDecision(**decision_data)
            
            logger.info(f"PortfolioAgent Decision for {symbol}: {decision.action}")
            return decision

        except Exception as e:
            logger.error(f"PortfolioAgent failed for {symbol}: {e}")
            # Safe fallback is always HOLD
            return PortfolioDecision(
                action="HOLD",
                reasoning=[f"LLM Error: {str(e)}. Defaulting to HOLD."]
            )
