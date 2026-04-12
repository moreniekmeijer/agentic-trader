from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AnalystRating = Literal["Buy", "Hold", "Sell"]


class FundamentalsSnapshot(BaseModel):
    symbol: str
    fetched_at: datetime

    pe_ratio: float | None
    forward_pe: float | None
    price_to_book: float | None

    revenue_growth_yoy: float | None
    earnings_growth_yoy: float | None

    profit_margin: float | None
    debt_to_equity: float | None
    return_on_equity: float | None

    analyst_rating: AnalystRating | None
    price_target: float | None
    