"""Compatibility exports for repository classes.

Prefer importing new code from ``agentic_trader.database.repositories``.
"""

from agentic_trader.database.repositories import BrokerRepository, TradeRepository, WatchlistRepository

__all__ = ["BrokerRepository", "TradeRepository", "WatchlistRepository"]
