from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agentic_trader.database.models import AgentVote, Decision, Trade


class AgentScorecard(BaseModel):
    agent: str
    closed_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0
    average_pnl: float = 0.0
    average_pnl_pct: float = 0.0
    win_rate: float = 0.0
    signals: dict[str, int] = Field(default_factory=dict)


def compute_agent_scorecards(
    session: Session,
    *,
    symbol: str | None = None,
    limit: int | None = None,
) -> list[AgentScorecard]:
    query = (
        session.query(AgentVote, Trade)
        .join(Decision, AgentVote.decision_id == Decision.id)
        .join(Trade, Trade.decision_id == Decision.id)
        .filter(Trade.closed_at.isnot(None))
        .filter(Trade.pnl.isnot(None))
        .filter(Trade.pnl_pct.isnot(None))
        .filter(Trade.needs_reconciliation.is_(False))
        .order_by(Trade.closed_at.desc())
    )
    if symbol:
        query = query.filter(Trade.symbol == symbol.upper())
    if limit is not None:
        query = query.limit(limit)

    grouped: dict[str, list[tuple[AgentVote, Trade]]] = {}
    for vote, trade in query.all():
        grouped.setdefault(vote.agent, []).append((vote, trade))

    scorecards = [_score_agent(agent, rows) for agent, rows in grouped.items()]
    return sorted(scorecards, key=lambda item: item.total_pnl, reverse=True)


def _score_agent(agent: str, rows: list[tuple[AgentVote, Trade]]) -> AgentScorecard:
    closed_trades = len(rows)
    total_pnl = sum(float(trade.pnl or 0.0) for _, trade in rows)
    total_pnl_pct = sum(float(trade.pnl_pct or 0.0) for _, trade in rows)
    winning_trades = sum(1 for _, trade in rows if (trade.pnl or 0.0) > 0)
    signals: dict[str, int] = {}
    for vote, _ in rows:
        signals[vote.signal] = signals.get(vote.signal, 0) + 1

    return AgentScorecard(
        agent=agent,
        closed_trades=closed_trades,
        winning_trades=winning_trades,
        total_pnl=total_pnl,
        average_pnl=total_pnl / closed_trades if closed_trades else 0.0,
        average_pnl_pct=total_pnl_pct / closed_trades if closed_trades else 0.0,
        win_rate=winning_trades / closed_trades if closed_trades else 0.0,
        signals=signals,
    )
