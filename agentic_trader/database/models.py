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
from sqlalchemy.dialects.postgresql import ARRAY
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
    # closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # close_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    decision_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("decisions.id"), nullable=True, index=True
    )
    decision: Mapped[Optional[Decision]] = relationship("Decision", back_populates="trade")
