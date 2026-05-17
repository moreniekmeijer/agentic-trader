"""Deprecated compatibility exports for repository classes.

Prefer importing new code from ``agentic_trader.database.repositories``.
Do not add repository implementations here.
"""

from agentic_trader.database.repositories import (
    BrokerRepository,
    OrderIntentRepository,
    TradeRepository,
    WatchlistRepository,
)

__all__ = ["BrokerRepository", "OrderIntentRepository", "TradeRepository", "WatchlistRepository"]
