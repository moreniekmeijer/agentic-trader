import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from agentic_trader.agents.models import AgentResponse
from agentic_trader.portfolio.policy import PortfolioPolicy
from agentic_trader.risk.models import RiskVerdict

logger = logging.getLogger(__name__)


class RiskEngine:
    def __init__(
        self,
        alpaca_controller,
        max_total_positions: int | None = None,
        min_confidence: float = 0.3,
        cooldown_minutes: int = 10,
        policy: PortfolioPolicy | None = None,
        sector_by_symbol: Mapping[str, str] | None = None,
    ):
        self.alpaca = alpaca_controller
        self.policy = policy or PortfolioPolicy.from_env()
        if max_total_positions is not None:
            self.policy.max_open_positions = max_total_positions
        self.max_total_positions = self.policy.max_open_positions
        self.sector_by_symbol = sector_by_symbol
        self.min_confidence = min_confidence
        self.cooldown = timedelta(minutes=cooldown_minutes)

        self._last_trade: dict[str, datetime] = {}

    def can_trade(self, response: AgentResponse) -> RiskVerdict:
        if response.confidence < self.min_confidence:
            return RiskVerdict(
                allowed=False,
                reason=f"low confidence ({response.confidence:.2f} < {self.min_confidence})",
            )

        if self._in_cooldown(response.symbol):
            elapsed = self._elapsed(response.symbol)
            return RiskVerdict(
                allowed=False,
                reason=f"cooldown active ({elapsed:.0f}s remaining)",
            )

        if response.signal == "BUY":
            account = self.alpaca.get_account()
            positions = self.alpaca.get_positions()

            if not self.policy.position_count_allows_new_buy(positions, response.symbol):
                return RiskVerdict(
                    allowed=False,
                    reason=f"max positions reached ({self.max_total_positions})",
                )

            if self.policy.available_cash_after_reserve(account) <= 0:
                return RiskVerdict(
                    allowed=False,
                    reason="cash reserve would be violated",
                )

            if response.entry_price is not None and response.stop_loss_price is not None:
                qty = self._allowed_qty_from_state(
                    response.symbol,
                    response.entry_price,
                    response.stop_loss_price,
                    response.conviction or "LOW",
                    account,
                    positions,
                )
                if qty <= 0:
                    return RiskVerdict(
                        allowed=False,
                        reason="position, cash, or stop-loss risk limit would be violated",
                    )

        return RiskVerdict(allowed=True)

    def get_allowed_qty(
        self, symbol: str, entry_price: float, stop_loss_price: float, conviction: str
    ) -> float:
        account = self.alpaca.get_account()
        positions = self.alpaca.get_positions()

        return self._allowed_qty_from_state(
            symbol,
            entry_price,
            stop_loss_price,
            conviction,
            account,
            positions,
        )

    def _allowed_qty_from_state(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: float,
        conviction: str,
        account: Any,
        positions: Sequence[Any],
    ) -> float:
        # Risk per share
        risk_per_share = abs(entry_price - stop_loss_price)
        if risk_per_share <= 0:
            logger.warning(
                f"Invalid bracket targets for {symbol}. Entry: {entry_price}, SL: {stop_loss_price}"
            )
            return 0.0

        return self.policy.allowed_buy_qty(
            account=account,
            positions=positions,
            symbol=symbol,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            conviction=conviction,
            cash_available=self.policy.available_cash_after_reserve(account),
            current_position_value=None,
            sector_value=self._sector_value(symbol, positions),
        )

    def register_trade(self, symbol: str) -> None:
        self._last_trade[symbol] = datetime.now(timezone.utc)

    def _in_cooldown(self, symbol: str) -> bool:
        last = self._last_trade.get(symbol)
        if last is None:
            return False
        return datetime.now(timezone.utc) - last < self.cooldown

    def _elapsed(self, symbol: str) -> float:
        """Remaining cooldown in seconds."""
        last = self._last_trade.get(symbol)
        if last is None:
            return 0.0
        remaining = self.cooldown - (datetime.now(timezone.utc) - last)
        return max(0.0, remaining.total_seconds())

    def _sector_value(self, symbol: str, positions: Sequence[Any]) -> float:
        sector = self.policy.sector_for(symbol, self.sector_by_symbol)
        if sector is None:
            return 0.0
        return self.policy.sector_values(positions, self.sector_by_symbol).get(sector, 0.0)
