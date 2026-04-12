import logging
from typing import Literal

from agentic_trader.agents.agent import BaseAgent
from agentic_trader.services.fundamentals.models import FundamentalsSnapshot

logger = logging.getLogger(__name__)

Signal = Literal["BUY", "SELL", "HOLD"]


class FundamentalsAgent (BaseAgent):
    def _compute_scores(self, data: FundamentalsSnapshot):
        score_buy = 0.0
        score_sell = 0.0
        reasons_buy: list[str] = []
        reasons_sell: list[str] = []

        # -----------------------------
        # P/E ratio
        # -----------------------------
        if data.pe_ratio is not None:
            if data.pe_ratio < 15:
                score_buy += 0.25
                reasons_buy.append(f"Low P/E ({data.pe_ratio:.1f})")
            elif data.pe_ratio < 25:
                score_buy += 0.15
                reasons_buy.append(f"Reasonable P/E ({data.pe_ratio:.1f})")
            elif data.pe_ratio > 50:
                score_sell += 0.20
                reasons_sell.append(f"High P/E ({data.pe_ratio:.1f})")

        # -----------------------------
        # Revenue growth
        # -----------------------------
        if data.revenue_growth_yoy is not None:
            if data.revenue_growth_yoy > 0.15:
                score_buy += 0.20
                reasons_buy.append(
                    f"Strong revenue growth ({data.revenue_growth_yoy:.0%})"
                )
            elif data.revenue_growth_yoy > 0.05:
                score_buy += 0.10
                reasons_buy.append(
                    f"Moderate revenue growth ({data.revenue_growth_yoy:.0%})"
                )
            elif data.revenue_growth_yoy < 0:
                score_sell += 0.15
                reasons_sell.append(
                    f"Negative revenue growth ({data.revenue_growth_yoy:.0%})"
                )

        # -----------------------------
        # Profit margin
        # -----------------------------
        if data.profit_margin is not None:
            if data.profit_margin > 0.20:
                score_buy += 0.20
                reasons_buy.append(f"Strong margin ({data.profit_margin:.0%})")
            elif data.profit_margin > 0.10:
                score_buy += 0.10
                reasons_buy.append(f"Healthy margin ({data.profit_margin:.0%})")
            elif data.profit_margin < 0:
                score_sell += 0.20
                reasons_sell.append(f"Negative margin ({data.profit_margin:.0%})")

        # -----------------------------
        # Debt to equity
        # -----------------------------
        if data.debt_to_equity is not None:
            if data.debt_to_equity < 0.5:
                score_buy += 0.10
                reasons_buy.append(
                    f"Low debt/equity ({data.debt_to_equity:.2f})"
                )
            if data.debt_to_equity > 2.0:
                score_sell += 0.15
                reasons_sell.append(
                    f"High debt/equity ({data.debt_to_equity:.2f})"
                )

        # -----------------------------
        # Analyst consensus
        # -----------------------------
        if data.analyst_rating == "Buy":
            score_buy += 0.15
            reasons_buy.append("Analyst consensus: Buy")
        elif data.analyst_rating == "Sell":
            score_sell += 0.15
            reasons_sell.append("Analyst consensus: Sell")

        return score_buy, score_sell, reasons_buy, reasons_sell