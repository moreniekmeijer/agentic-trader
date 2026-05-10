import logging
from datetime import datetime, timedelta, timezone

from agentic_trader.agents.models import AgentResponse
from agentic_trader.risk.models import RiskVerdict

logger = logging.getLogger(__name__)


class RiskEngine:
    def __init__(
        self,
        alpaca_controller,
        max_total_positions: int = 100,
        min_confidence: float = 0.3,
        cooldown_minutes: int = 10,
    ):
        self.alpaca = alpaca_controller
        self.max_total_positions = max_total_positions
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

        positions = self.alpaca.get_positions()
        if len(positions) >= self.max_total_positions:
            return RiskVerdict(
                allowed=False,
                reason=f"max positions reached ({self.max_total_positions})",
            )

        return RiskVerdict(allowed=True)

    def get_allowed_qty(self, symbol: str, entry_price: float, stop_loss_price: float, conviction: str) -> float:
        # Risk percentage based on conviction
        risk_map = {"LOW": 0.005, "MEDIUM": 0.01, "HIGH": 0.02}
        risk_pct = risk_map.get(conviction.upper(), 0.005)
        
        account = self.alpaca.get_account()
        equity = float(account.equity)
        
        # Risk amount in dollars
        risk_amount = equity * risk_pct
        
        # Risk per share
        risk_per_share = abs(entry_price - stop_loss_price)
        if risk_per_share <= 0:
            logger.warning(f"Invalid bracket targets for {symbol}. Entry: {entry_price}, SL: {stop_loss_price}")
            return 0.0
            
        qty = int(risk_amount / risk_per_share)
        
        # Cap by buying power
        buying_power = float(account.buying_power)
        if entry_price > 0:
            max_qty_by_power = int(buying_power / entry_price)
            qty = min(qty, max_qty_by_power)
            
        return max(0, float(qty))

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
