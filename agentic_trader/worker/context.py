from __future__ import annotations

from pydantic import BaseModel

from agentic_trader.controller.alpaca_controller import AlpacaController
from agentic_trader.data import sp500_symbols
from agentic_trader.risk.engine import RiskEngine

SCAN_INTERVAL_SECONDS = 24 * 60 * 60
TRADE_INTERVAL_SECONDS = 24 * 60 * 60


class WorkerContext(BaseModel):
    """Runtime dependencies shared by worker handlers."""

    model_config = {"arbitrary_types_allowed": True}

    alpaca_controller: AlpacaController
    risk_engine: RiskEngine
    symbols: list[str]
    scan_interval_seconds: int = SCAN_INTERVAL_SECONDS
    trade_interval_seconds: int = TRADE_INTERVAL_SECONDS


def build_worker_context() -> WorkerContext:
    alpaca_controller = AlpacaController()

    return WorkerContext(
        alpaca_controller=alpaca_controller,
        risk_engine=RiskEngine(alpaca_controller),
        symbols=sp500_symbols[:10],
    )
