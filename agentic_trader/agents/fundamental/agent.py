import logging
from typing import Literal

from agentic_trader.agents.agent import BaseAgent
from agentic_trader.services.fundamentals.models import FundamentalsSnapshot
from agentic_trader.services.fundamentals.sector.baselines import get_baseline

logger = logging.getLogger(__name__)

Signal = Literal["BUY", "SELL", "HOLD"]

_WEIGHTS = {
    "growth": 0.18,
    "pe": 0.22,
    "margin": 0.18,
    "de": 0.18,
    "roe": 0.18,
    "analyst": 0.06,
}
assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


class FundamentalsAgent(BaseAgent):
    def _score_relative(
        self,
        value: float,
        target: float,
        weight: float,
        positive_is_good: bool = True,
    ) -> tuple[float, float, float]:
        """
        Scores a metric relative to its sector baseline.

        Returns (buy_score, sell_score, deviation) where deviation is in [-1, 1].
        Raises ValueError if target is zero — callers should guard before calling.
        """
        if target == 0:
            logger.warning("_score_relative called with target=0; skipping metric.")
            return 0.0, 0.0, 0.0

        deviation = (value - target) / abs(target)
        deviation = max(min(deviation, 1.0), -1.0)

        if positive_is_good:
            if deviation > 0:
                return deviation * weight, 0.0, deviation
            else:
                return 0.0, abs(deviation) * weight, deviation
        else:
            if deviation < 0:
                return abs(deviation) * weight, 0.0, deviation
            else:
                return 0.0, deviation * weight, deviation

    def _score_growth(self, growth: float) -> tuple[float, float, list[str], list[str]]:
        """
        Scores revenue growth on the same [-1, 1] deviation scale as other
        metrics, capped at ±50% growth as the reference ceiling.
        """
        reasons_buy: list[str] = []
        reasons_sell: list[str] = []
        weight = _WEIGHTS["growth"]
        ceiling = 0.50  # beyond this, treat as maximum signal

        clamped = max(min(growth, ceiling), -ceiling)
        deviation = clamped / ceiling

        if deviation > 0:
            score = deviation * weight
            reasons_buy.append(f"Revenue growth ({growth:.0%})")
            return score, 0.0, reasons_buy, reasons_sell
        else:
            score = abs(deviation) * weight
            reasons_sell.append(f"Revenue decline ({growth:.0%})")
            return 0.0, score, reasons_buy, reasons_sell

    def _score_pe(
        self,
        pe: float,
        growth: float | None,
        baseline_pe: float,
    ) -> tuple[float, float, list[str], list[str]]:
        """
        Scores P/E ratio relative to sector baseline with an optional
        growth adjustment (PEG-style).

        The growth adjustment is bounded to prevent extreme distortion:
        a -50% revenue collapse cannot more than double the adjusted P/E,
        and a +200% hypergrowth year cannot shrink it below 33% of face value.
        """
        reasons_buy: list[str] = []
        reasons_sell: list[str] = []

        if pe <= 0:
            logger.debug("Skipping P/E score: non-positive P/E (%.2f)", pe)
            return 0.0, 0.0, reasons_buy, reasons_sell

        if growth is not None and growth > 0:
            bounded_growth = min(growth, 1.0)
            adj_pe = pe / (1 + bounded_growth)
        else:
            adj_pe = pe

        buy, sell, dev = self._score_relative(
            value=adj_pe,
            target=baseline_pe,
            weight=_WEIGHTS["pe"],
            positive_is_good=False,
        )

        if dev < 0:
            reasons_buy.append(f"Undervalued vs sector P/E ({adj_pe:.1f} vs {baseline_pe:.1f})")
        else:
            reasons_sell.append(f"Expensive vs sector P/E ({adj_pe:.1f} vs {baseline_pe:.1f})")

        return buy, sell, reasons_buy, reasons_sell

    def _compute_scores(self, data: FundamentalsSnapshot) -> tuple[float, float, list[str], list[str]]:
        score_buy = 0.0
        score_sell = 0.0
        reasons_buy: list[str] = []
        reasons_sell: list[str] = []

        baseline = get_baseline(data.sector)
        growth = data.revenue_growth_yoy

        # --- Growth ---
        if growth is not None:
            b, s, rb, rs = self._score_growth(growth)
            score_buy += b
            score_sell += s
            reasons_buy += rb
            reasons_sell += rs

        # --- P/E (growth-adjusted) ---
        if data.pe_ratio is not None:
            b, s, rb, rs = self._score_pe(data.pe_ratio, growth, baseline["pe"])
            score_buy += b
            score_sell += s
            reasons_buy += rb
            reasons_sell += rs

        # --- Profit margin ---
        if data.profit_margin is not None:
            margin = data.profit_margin
            target = baseline["profit_margin"]
            buy, sell, dev = self._score_relative(
                value=margin,
                target=target,
                weight=_WEIGHTS["margin"],
                positive_is_good=True,
            )
            score_buy += buy
            score_sell += sell
            if dev > 0:
                reasons_buy.append(f"Above-sector margin ({margin:.0%} vs {target:.0%})")
            else:
                reasons_sell.append(f"Below-sector margin ({margin:.0%} vs {target:.0%})")

        # --- Debt-to-equity ---
        if data.debt_to_equity is not None:
            de = data.debt_to_equity
            target = baseline["de_ratio"]
            buy, sell, dev = self._score_relative(
                value=de,
                target=target,
                weight=_WEIGHTS["de"],
                positive_is_good=False,
            )
            score_buy += buy
            score_sell += sell
            if dev < 0:
                reasons_buy.append(f"Low leverage vs sector ({de:.2f} vs {target:.2f})")
            else:
                reasons_sell.append(f"High leverage vs sector ({de:.2f} vs {target:.2f})")

        # --- Return on equity ---
        if data.return_on_equity is not None:
            roe = data.return_on_equity
            target = baseline["roe"]

            if roe < -0.5:
                # Extreme negative ROE (e.g. post-buyback distortion or deep losses)
                score_sell += _WEIGHTS["roe"]
                reasons_sell.append(f"Severely negative ROE ({roe:.0%})")
            else:
                buy, sell, dev = self._score_relative(
                    value=roe,
                    target=target,
                    weight=_WEIGHTS["roe"],
                    positive_is_good=True,
                )
                score_buy += buy
                score_sell += sell
                if dev > 0:
                    reasons_buy.append(f"Strong ROE vs sector ({roe:.0%} vs {target:.0%})")
                else:
                    reasons_sell.append(f"Weak ROE vs sector ({roe:.0%} vs {target:.0%})")

        # --- Analyst consensus ---
        if data.analyst_rating == "Buy":
            score_buy += _WEIGHTS["analyst"]
            reasons_buy.append("Analyst consensus: Buy")
        elif data.analyst_rating == "Sell":
            score_sell += _WEIGHTS["analyst"]
            reasons_sell.append("Analyst consensus: Sell")

        return score_buy, score_sell, reasons_buy, reasons_sell
