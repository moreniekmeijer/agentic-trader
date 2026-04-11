import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RiskEngine:
    def __init__(
        self,
        alpaca_controller,
        max_position_size=5,
        max_total_positions=5,
        min_confidence=0.2,
        cooldown_minutes=10,
    ):
        self.alpaca = alpaca_controller
        self.max_position_size = max_position_size
        self.max_total_positions = max_total_positions
        self.min_confidence = min_confidence
        self.cooldown_minutes = cooldown_minutes

        self.last_trade_time = {}

    def can_trade(self, agent_response):
        symbol = agent_response.symbol

        # --- 1. confidence check ---
        if agent_response.confidence < self.min_confidence:
            logger.info(f"Risk: skip {symbol}, low confidence")
            return False

        # --- 2. cooldown check ---
        now = datetime.now()
        last_time = self.last_trade_time.get(symbol)

        if last_time and (now - last_time) < timedelta(minutes=self.cooldown_minutes):
            logger.info(f"Risk: skip {symbol}, cooldown active")
            return False

        # --- 3. max positions check ---
        positions = self.alpaca.get_positions()
        if len(positions) >= self.max_total_positions:
            logger.info("Risk: max total positions reached")
            return False

        return True

    def get_allowed_qty(self, symbol):
        current_qty = self.alpaca.get_position(symbol)

        allowed = self.max_position_size - current_qty
        return max(0, allowed)

    def register_trade(self, symbol):
        self.last_trade_time[symbol] = datetime.now()
