import json
import logging
import os
from typing import List

from groq import Groq

from agentic_trader.agents.models import AgentVote

logger = logging.getLogger(__name__)


class SentimentAgent:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = model

    def generate_signal(self, symbol: str, news_articles: List) -> AgentVote:
        if not news_articles:
            return AgentVote(
                agent="sentiment",
                symbol=symbol,
                signal="NEUTRAL",
                confidence=0.5,
                reasoning=["No recent news articles found for analysis."],
                weight=0.0
            )

        news_context = []
        for art in news_articles:
            # Handle both object and dict
            headline = getattr(art, "headline", art.get("headline") if isinstance(art, dict) else "No Headline")
            summary = getattr(art, "summary", art.get("summary") if isinstance(art, dict) else "No Summary")
            source = getattr(art, "source", art.get("source") if isinstance(art, dict) else "Unknown Source")
            news_context.append(f"Headline: {headline}\nSummary: {summary}\nSource: {source}")

        news_str = "\n\n".join(news_context)

        prompt = f"""
You are a Senior Sentiment Analyst specializing in the stock market.
Your task is to analyze the following recent news articles for ticker symbol {symbol} 
and provide a sentiment-based trading signal.

Focus on:
1. Overall tone (Bullish, Bearish, or Neutral).
2. Key catalysts (Earnings, product launches, lawsuits, macro shifts).
3. Impact severity (High, Medium, Low).

Recent News:
{news_str}

Output your analysis strictly in JSON format with these keys:
- signal: "BUY", "SELL", or "NEUTRAL"
- confidence: 0.0 to 1.0
- reasoning: A list of 3-5 concise bullet points.

JSON Response:"""

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a logical financial analyst. Output ONLY valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            response = json.loads(completion.choices[0].message.content)

            return AgentVote(
                agent="sentiment",
                symbol=symbol,
                signal=response.get("signal", "NEUTRAL").upper(),
                confidence=float(response.get("confidence", 0.5)),
                reasoning=response.get("reasoning", ["No specific reasoning provided."]),
                weight=1.0
            )

        except Exception as e:
            logger.error(f"Sentiment analysis failed for {symbol}: {e}")
            return AgentVote(
                agent="sentiment",
                symbol=symbol,
                signal="NEUTRAL",
                confidence=0.5,
                reasoning=[f"Error during analysis: {e}"],
                weight=0.0
            )
