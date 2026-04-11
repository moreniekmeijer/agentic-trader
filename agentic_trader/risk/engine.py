import logging
from datetime import datetime, timedelta, timezone

from agentic_trader.agents.technical.models import TechnicalAgentResponse
from agentic_trader.risk.models import RiskVerdict

logger = logging.getLogger(__name__)


class RiskEngine:
    def __init__(
        self,
        alpaca_controller,
        max_position_size: int = 5,
        max_total_positions: int = 5,
        min_confidence: float = 0.2,
        cooldown_minutes: int = 10,
    ):
        self.alpaca = alpaca_controller
        self.max_position_size = max_position_size
        self.max_total_positions = max_total_positions
        self.min_confidence = min_confidence
        self.cooldown = timedelta(minutes=cooldown_minutes)

        self._last_trade: dict[str, datetime] = {}

    def can_trade(self, response: TechnicalAgentResponse) -> RiskVerdict:
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

        positions = self.alpaca.get_positions()
        if len(positions) >= self.max_total_positions:
            return RiskVerdict(
                allowed=False,
                reason=f"max positions reached ({self.max_total_positions})",
            )

        return RiskVerdict(allowed=True)

    def get_allowed_qty(self, symbol: str) -> int:
        current_qty = self.alpaca.get_position(symbol)
        return max(0, self.max_position_size - current_qty)

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
