"""Deprecated compatibility exports for repository classes.

Prefer importing new code from ``agentic_trader.database.repositories``.
Do not add repository implementations here.
"""

from agentic_trader.database.repositories import BrokerRepository, TradeRepository, WatchlistRepository

__all__ = ["BrokerRepository", "TradeRepository", "WatchlistRepository"]
