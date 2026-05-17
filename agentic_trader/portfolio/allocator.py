from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agentic_trader.agents.models import AgentResponse
from agentic_trader.database.models import OrderIntent
from agentic_trader.portfolio.policy import PortfolioPolicy


class PortfolioAllocator:
    """Build deterministic order intents from ranked signals and live broker state."""

    def __init__(self, policy: PortfolioPolicy | None = None):
        self.policy = policy or PortfolioPolicy.from_env()

    def allocate(
        self,
        candidates: Sequence[AgentResponse],
        *,
        account: Any,
        positions: Sequence[Any],
        sector_by_symbol: Mapping[str, str] | None = None,
    ) -> list[OrderIntent]:
        intents: list[OrderIntent] = []
        intents.extend(self._sell_intents(candidates, positions))
        intents.extend(self._buy_intents(candidates, account, positions, sector_by_symbol))
        return intents

    def _sell_intents(
        self,
        candidates: Sequence[AgentResponse],
        positions: Sequence[Any],
    ) -> list[OrderIntent]:
        intents: list[OrderIntent] = []
        sell_candidates = [
            candidate
            for candidate in candidates
            if str(candidate.signal).upper() in {"SELL", "EXIT", "REDUCE"}
        ]
        ranked_sells = sorted(
            sell_candidates,
            key=lambda candidate: candidate.confidence,
            reverse=True,
        )

        for candidate in ranked_sells:
            position = self.policy.find_position(positions, candidate.symbol)
            if position is None:
                continue

            qty = self.policy.position_qty(position)
            if str(candidate.signal).upper() == "REDUCE":
                qty = qty / 2
            if qty <= 0:
                continue

            intents.append(
                OrderIntent(
                    symbol=candidate.symbol,
                    side="sell",
                    qty=qty,
                    order_type="market",
                    rationale=_rationale(candidate),
                    data={
                        "confidence": candidate.confidence,
                        "source_signal": candidate.signal,
                    },
                )
            )

        return intents

    def _buy_intents(
        self,
        candidates: Sequence[AgentResponse],
        account: Any,
        positions: Sequence[Any],
        sector_by_symbol: Mapping[str, str] | None,
    ) -> list[OrderIntent]:
        buy_candidates = [
            candidate
            for candidate in sorted(
                _signals(candidates, "BUY"),
                key=lambda item: item.confidence,
                reverse=True,
            )
            if candidate.entry_price is not None and candidate.stop_loss_price is not None
        ]
        if not buy_candidates:
            return []

        cash_available = self.policy.available_cash_after_reserve(account)
        if cash_available <= 0:
            return []

        sector_values = self.policy.sector_values(positions, sector_by_symbol)
        total_confidence = sum(max(0.0, candidate.confidence) for candidate in buy_candidates)
        if total_confidence <= 0:
            return []

        intents: list[OrderIntent] = []
        equity = self.policy.equity(account)

        for candidate in buy_candidates:
            if cash_available <= 0:
                break
            if not self.policy.position_count_allows_new_buy(positions, candidate.symbol):
                continue

            sector = self.policy.sector_for(candidate.symbol, sector_by_symbol)
            sector_value = sector_values.get(sector, 0.0) if sector else 0.0
            position = self.policy.find_position(positions, candidate.symbol)
            current_position_value = (
                self.policy.position_market_value(position) if position is not None else 0.0
            )
            candidate_cash = cash_available * (max(0.0, candidate.confidence) / total_confidence)

            qty = self.policy.allowed_buy_qty(
                account=account,
                positions=positions,
                symbol=candidate.symbol,
                entry_price=candidate.entry_price,
                stop_loss_price=candidate.stop_loss_price,
                conviction=candidate.conviction,
                cash_available=candidate_cash,
                current_position_value=current_position_value,
                sector_value=sector_value,
            )
            if qty <= 0:
                continue

            order_value = qty * candidate.entry_price
            cash_available = max(0.0, cash_available - order_value)
            if sector:
                sector_values[sector] = sector_value + order_value

            target_weight = 0.0
            if equity > 0:
                target_weight = (current_position_value + order_value) / equity

            intents.append(
                OrderIntent(
                    symbol=candidate.symbol,
                    side="buy",
                    qty=qty,
                    order_type="limit",
                    rationale=_rationale(candidate),
                    data={
                        "confidence": candidate.confidence,
                        "entry_price": candidate.entry_price,
                        "stop_loss_price": candidate.stop_loss_price,
                        "take_profit_price": candidate.take_profit_price,
                        "target_weight": target_weight,
                        "sector": sector,
                    },
                )
            )

        return intents


def _signals(candidates: Sequence[AgentResponse], signal: str) -> list[AgentResponse]:
    return [candidate for candidate in candidates if str(candidate.signal).upper() == signal]


def _rationale(candidate: AgentResponse) -> str:
    reasoning = " ".join(candidate.reasoning)
    return reasoning or f"{candidate.signal} signal at {candidate.confidence:.2f} confidence"
