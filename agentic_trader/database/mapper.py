from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agentic_trader.database.models import (
    AgentVote,
    Decision,
    Trade,
    WatchlistEntry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# WATCHLIST
# ---------------------------------------------------------------------------

def to_watchlist_entry(
    *,
    symbol: str,
    added_by: str,
    thesis: str,
    invalidation: str,
    horizon: str,
    review_after: datetime | None,
) -> WatchlistEntry:
    return WatchlistEntry(
        symbol=symbol.upper(),
        added_by=added_by,
        thesis=thesis,
        invalidation=invalidation,
        horizon=horizon,
        review_after=review_after,
    )


# ---------------------------------------------------------------------------
# DECISIONS + VOTES
# ---------------------------------------------------------------------------

def to_decision(
    *,
    symbol: str,
    signal: str,
    confidence: float,
    reasoning: list[str],
) -> Decision:
    return Decision(
        symbol=symbol.upper(),
        signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        executed=False,
    )


def to_agent_vote(
    *,
    symbol: str,
    agent: str,
    signal: str,
    confidence: float,
    reasoning: list[str],
    weight: float,
    decision_id: int,
) -> AgentVote:
    return AgentVote(
        symbol=symbol.upper(),
        agent=agent,
        signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        weight=weight,
        decision_id=decision_id,
    )


# ---------------------------------------------------------------------------
# TRADE
# ---------------------------------------------------------------------------

def extract_price(order: Any) -> float | None:
    """Extraheer de prijs uit een Alpaca order object."""
    return (
        getattr(order, "filled_avg_price", None)
        or getattr(order, "avg_fill_price", None)
        or getattr(order, "price", None)
        or None
    )


def extract_order_id(order: Any) -> str:
    return str(getattr(order, "id", ""))


def to_trade(
    *,
    symbol: str,
    side: str,
    qty: float,
    order: Any,
    decision_id: int,
) -> Trade:
    price = extract_price(order)

    return Trade(
        symbol=symbol.upper(),
        side=side,
        qty=qty,
        price=price,
        alpaca_order_id=extract_order_id(order),
        decision_id=decision_id,
    )


# ---------------------------------------------------------------------------
# UPDATE HELPERS (mutations)
# ---------------------------------------------------------------------------

def mark_decision_blocked(decision: Decision, reason: str) -> None:
    decision.blocked_reason = reason


def mark_decision_executed(decision: Decision) -> None:
    decision.executed = True


def close_trade(
    trade: Trade,
    close_price: float,
) -> None:
    trade.closed_at = utcnow()
    trade.close_price = close_price

    assert trade.price is not None
    trade.pnl = (close_price - trade.price) * trade.qty
    trade.pnl_pct = (close_price - trade.price) / trade.price