import logging
from datetime import datetime, timezone

import yfinance as yf

from agentic_trader.services.fundamentals.models import AnalystRating, FundamentalsSnapshot
from agentic_trader.services.fundamentals.provider import FundamentalsProvider

logger = logging.getLogger(__name__)

_RATING_MAP: dict[str, AnalystRating] = {
    "buy": "Buy",
    "strong buy": "Buy",
    "outperform": "Buy",
    "overweight": "Buy",
    "hold": "Hold",
    "neutral": "Hold",
    "market perform": "Hold",
    "equal-weight": "Hold",
    "sell": "Sell",
    "underperform": "Sell",
    "underweight": "Sell",
    "strong sell": "Sell",
}


def _safe_float(info: dict, key: str) -> float | None:
    val = info.get(key)
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _parse_rating(info: dict) -> AnalystRating | None:
    raw = info.get("recommendationKey", "")
    if not raw:
        return None
    return _RATING_MAP.get(raw.lower())


class YahooFundamentalsProvider(FundamentalsProvider):
    def get_fundamentals(self, symbol: str) -> FundamentalsSnapshot:
        info = yf.Ticker(symbol).info

        return FundamentalsSnapshot(
            symbol=symbol,
            fetched_at=datetime.now(timezone.utc),
            pe_ratio=_safe_float(info, "trailingPE"),
            forward_pe=_safe_float(info, "forwardPE"),
            price_to_book=_safe_float(info, "priceToBook"),
            revenue_growth_yoy=_safe_float(info, "revenueGrowth"),
            earnings_growth_yoy=_safe_float(info, "earningsGrowth"),
            profit_margin=_safe_float(info, "profitMargins"),
            debt_to_equity=_safe_float(info, "debtToEquity"),
            return_on_equity=_safe_float(info, "returnOnEquity"),
            analyst_rating=_parse_rating(info),
            price_target=_safe_float(info, "targetMeanPrice"),
            sector=info.get("sector"),
            industry=info.get("industry"),
        )