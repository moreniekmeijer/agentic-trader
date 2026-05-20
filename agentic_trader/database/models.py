"""
Database models voor agentic-trader.

Postgres via SQLAlchemy 2.x (declarative style).
Setup: pip install sqlalchemy psycopg2-binary alembic
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


class WatchlistEntry(Base):
    """
    Een aandeel dat bewust gevolgd wordt, met thesis en invalidation.
    Long-term: leeft totdat is_active=False of invalidation geraakt wordt.
    """

    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    added_by: Mapped[str] = mapped_column(String(50))  # "watchlist_agent" | "manual"

    thesis: Mapped[str] = mapped_column(Text)  # waarom interessant
    invalidation: Mapped[str] = mapped_column(Text)  # wanneer thesis vervalt
    horizon: Mapped[str] = mapped_column(String(10))  # "short" | "medium" | "long"
    review_after: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# State Management (Replaces in-memory WorkerState)
# ---------------------------------------------------------------------------


class MarketState(Base):
    """
    Persisted state for the active scan shortlist.
    """

    __tablename__ = "market_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)  # e.g. 'active_shortlist'
    symbols: Mapped[list] = mapped_column(ARRAY(String))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FundamentalsData(Base):
    """
    Cached fundamental data per symbol to avoid fetching constantly.
    """

    __tablename__ = "fundamentals_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    data: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------------------
# Broker audit state
# ---------------------------------------------------------------------------


class BrokerSnapshotRecord(Base):
    """Account-level broker snapshot captured from Alpaca."""

    __tablename__ = "broker_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    account_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    buying_power: Mapped[float] = mapped_column(Float, nullable=False)
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    portfolio_value: Mapped[float] = mapped_column(Float, nullable=False)
    invested_value: Mapped[float] = mapped_column(Float, nullable=False)
    position_count: Mapped[int] = mapped_column(Integer, nullable=False)
    open_order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)


class OrderIntent(Base):
    """Local intended action before broker submission."""

    __tablename__ = "order_intents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    order_type: Mapped[str] = mapped_column(String(30), nullable=False, default="market")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    broker_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class OrderLifecycle(Base):
    """Latest broker-visible order lifecycle state."""

    __tablename__ = "order_lifecycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broker_order_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    client_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    order_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    order_class: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    filled_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    filled_avg_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    limit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    broker_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)


class PositionMeta(Base):
    """Local thesis metadata for an open position."""

    __tablename__ = "position_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    decision_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("decisions.id"), nullable=True)
    thesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    invalidation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_horizon_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class PositionReviewRecord(Base):
    """Accepted or rejected de-risking review for an open position."""

    __tablename__ = "position_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning: Mapped[list] = mapped_column(ARRAY(Text))
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)


# ---------------------------------------------------------------------------
# Agent votes
# ---------------------------------------------------------------------------


class AgentVote(Base):
    """
    Elke individuele agent-analyse per symbool per cyclus.
    Koppelt aan een Decision zodat je achteraf kunt analyseren
    welke agents gelijk hadden.
    """

    __tablename__ = "agent_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    agent: Mapped[str] = mapped_column(String(50))  # "technical" | "fundamentals"
    signal: Mapped[str] = mapped_column(String(10))  # "BUY" | "SELL" | "HOLD"
    confidence: Mapped[float] = mapped_column(Float)
    reasoning: Mapped[list] = mapped_column(ARRAY(Text))
    weight: Mapped[float] = mapped_column(Float)  # gewicht in DiscussionAgent

    decision_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("decisions.id"), nullable=True, index=True
    )
    decision: Mapped[Optional[Decision]] = relationship("Decision", back_populates="votes")


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


class Decision(Base):
    """
    De geaggregeerde beslissing per symbool per cyclus (output DiscussionAgent).
    Bevat alle votes en het eindoordeel.
    """

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    signal: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float] = mapped_column(Float)
    reasoning: Mapped[list] = mapped_column(ARRAY(Text))

    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # risk engine reden
    thesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    invalidation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_horizon_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    setup_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    evidence: Mapped[list] = mapped_column(ARRAY(Text), default=list)
    market_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)

    votes: Mapped[list[AgentVote]] = relationship("AgentVote", back_populates="decision")
    trade: Mapped[Optional[Trade]] = relationship("Trade", back_populates="decision", uselist=False)


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------


class Trade(Base):
    """
    Uitgevoerde trade, gekoppeld aan Alpaca order en aan de Decision die hem veroorzaakte.
    PnL wordt achteraf ingevuld (bij sluiting positie).
    """

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    side: Mapped[str] = mapped_column(String(5))  # "buy" | "sell"
    qty: Mapped[float] = mapped_column(Float)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    alpaca_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)

    # Ingevuld bij sluiting
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    close_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    needs_reconciliation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reconciliation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    decision_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("decisions.id"), nullable=True, index=True
    )
    decision: Mapped[Optional[Decision]] = relationship("Decision", back_populates="trade")


# ---------------------------------------------------------------------------
# Trade Journal (Reflection Loop)
# ---------------------------------------------------------------------------


class TradeJournal(Base):
    """
    Stores AI reflections on closed trades.
    The Synthesizer will read past journals for a symbol to learn from its mistakes.
    """

    __tablename__ = "trade_journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[int] = mapped_column(Integer, ForeignKey("trades.id"), nullable=False, unique=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # The reflection content generated by the Reflector Agent
    reflection: Mapped[str] = mapped_column(Text, nullable=False)

    trade: Mapped[Trade] = relationship("Trade")
