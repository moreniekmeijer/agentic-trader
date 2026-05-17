from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from agentic_trader.database.models import AgentVote, Decision, Trade, TradeJournal
from agentic_trader.learning.models import (
    AgentVoteLearningSnapshot,
    DecisionLearningSnapshot,
    LearningQuery,
    RejectedRecommendationSnapshot,
    TradeOutcomeSnapshot,
)


class LearningJournal:
    """Read and write learning observations without duplicating broker-confirmed facts."""

    def __init__(self, session: Session):
        self.session = session

    def recent_lessons(self, symbol: str, limit: int = 5) -> list[str]:
        entries = (
            self.session.query(TradeJournal)
            .filter_by(symbol=symbol.upper())
            .order_by(TradeJournal.created_at.desc())
            .limit(limit)
            .all()
        )

        return [entry.reflection for entry in entries if entry.reflection]

    def closed_trades_without_reflection(self, limit: int | None = None) -> list[Trade]:
        query = (
            self.session.query(Trade)
            .options(joinedload(Trade.decision).joinedload(Decision.votes))
            .filter(Trade.closed_at.isnot(None))
            .filter(Trade.pnl.isnot(None))
            .filter(Trade.needs_reconciliation.is_(False))
            .filter(~Trade.id.in_(self.session.query(TradeJournal.trade_id)))
            .order_by(Trade.closed_at.asc())
        )
        if limit is not None:
            query = query.limit(limit)

        return query.all()

    def record_reflection(self, trade: Trade, reflection: str) -> TradeJournal:
        existing = self.session.query(TradeJournal).filter_by(trade_id=trade.id).first()
        if existing is not None:
            return existing

        journal = TradeJournal(trade_id=trade.id, symbol=trade.symbol, reflection=reflection)
        self.session.add(journal)

        return journal

    def decision_contexts(self, query: LearningQuery | None = None) -> list[DecisionLearningSnapshot]:
        query = query or LearningQuery()
        decisions = self._decision_query(query).limit(query.limit).all()

        return [self.decision_snapshot(decision) for decision in decisions]

    def rejected_recommendations(
        self,
        query: LearningQuery | None = None,
    ) -> list[RejectedRecommendationSnapshot]:
        query = query or LearningQuery()
        decisions = (
            self._decision_query(query)
            .filter(Decision.blocked_reason.isnot(None))
            .limit(query.limit)
            .all()
        )

        return [
            RejectedRecommendationSnapshot(
                **self.decision_snapshot(decision).model_dump(),
                rejected_rule=decision.blocked_reason or "unknown",
            )
            for decision in decisions
        ]

    def trade_outcomes(self, query: LearningQuery | None = None) -> list[TradeOutcomeSnapshot]:
        query = query or LearningQuery()
        trades = self._trade_query(query).limit(query.limit).all()

        return [self.trade_outcome_snapshot(trade) for trade in trades]

    def decision_snapshot(self, decision: Decision) -> DecisionLearningSnapshot:
        return DecisionLearningSnapshot(
            decision_id=decision.id,
            symbol=decision.symbol,
            timestamp=decision.timestamp,
            action=decision.signal,
            confidence=decision.confidence,
            reasoning=decision.reasoning or [],
            executed=decision.executed,
            blocked_reason=decision.blocked_reason,
            thesis=getattr(decision, "thesis", None),
            invalidation=getattr(decision, "invalidation", None),
            expected_horizon_days=getattr(decision, "expected_horizon_days", None),
            sector=getattr(decision, "sector", None),
            setup_type=getattr(decision, "setup_type", None),
            evidence=getattr(decision, "evidence", None) or [],
            market_snapshot=getattr(decision, "market_snapshot", None),
            votes=[_vote_snapshot(vote) for vote in decision.votes],
        )

    def trade_outcome_snapshot(self, trade: Trade) -> TradeOutcomeSnapshot:
        assert trade.closed_at is not None
        assert trade.price is not None
        assert trade.close_price is not None
        assert trade.pnl is not None
        assert trade.pnl_pct is not None

        opened_at = _as_aware(trade.timestamp)
        closed_at = _as_aware(trade.closed_at)
        journal = self.session.query(TradeJournal).filter_by(trade_id=trade.id).first()

        return TradeOutcomeSnapshot(
            trade_id=trade.id,
            symbol=trade.symbol,
            opened_at=opened_at,
            closed_at=closed_at,
            side=trade.side,
            qty=trade.qty,
            entry_price=trade.price,
            close_price=trade.close_price,
            realized_pnl=trade.pnl,
            realized_pnl_pct=trade.pnl_pct,
            holding_days=max(0, (closed_at - opened_at).days),
            exit_reason=_exit_reason(trade),
            decision=self.decision_snapshot(trade.decision) if trade.decision else None,
            reflection=journal.reflection if journal else None,
        )

    def _decision_query(self, query: LearningQuery):
        decision_query = (
            self.session.query(Decision)
            .options(joinedload(Decision.votes))
            .order_by(Decision.timestamp.desc())
        )
        if query.symbol:
            decision_query = decision_query.filter(Decision.symbol == query.symbol.upper())
        if query.sector:
            decision_query = decision_query.filter(Decision.sector == query.sector)
        if query.setup_type:
            decision_query = decision_query.filter(Decision.setup_type == query.setup_type)
        if query.min_horizon_days is not None:
            decision_query = decision_query.filter(Decision.expected_horizon_days >= query.min_horizon_days)
        if query.max_horizon_days is not None:
            decision_query = decision_query.filter(Decision.expected_horizon_days <= query.max_horizon_days)
        if query.agent:
            decision_query = (
                decision_query.join(AgentVote, AgentVote.decision_id == Decision.id)
                .filter(AgentVote.agent == query.agent)
                .distinct()
            )

        return decision_query

    def _trade_query(self, query: LearningQuery):
        trade_query = (
            self.session.query(Trade)
            .options(joinedload(Trade.decision).joinedload(Decision.votes))
            .filter(Trade.closed_at.isnot(None))
            .filter(Trade.price.isnot(None))
            .filter(Trade.close_price.isnot(None))
            .filter(Trade.pnl.isnot(None))
            .filter(Trade.pnl_pct.isnot(None))
            .filter(Trade.needs_reconciliation.is_(False))
            .order_by(Trade.closed_at.desc())
        )
        if query.symbol:
            trade_query = trade_query.filter(Trade.symbol == query.symbol.upper())
        if (
            query.sector
            or query.setup_type
            or query.agent
            or query.min_horizon_days is not None
            or query.max_horizon_days is not None
        ):
            trade_query = trade_query.join(Decision, Trade.decision_id == Decision.id)
        if query.sector:
            trade_query = trade_query.filter(Decision.sector == query.sector)
        if query.setup_type:
            trade_query = trade_query.filter(Decision.setup_type == query.setup_type)
        if query.min_horizon_days is not None:
            trade_query = trade_query.filter(Decision.expected_horizon_days >= query.min_horizon_days)
        if query.max_horizon_days is not None:
            trade_query = trade_query.filter(Decision.expected_horizon_days <= query.max_horizon_days)
        if query.agent:
            trade_query = (
                trade_query.join(AgentVote, AgentVote.decision_id == Decision.id)
                .filter(AgentVote.agent == query.agent)
                .distinct()
            )

        return trade_query


def _vote_snapshot(vote: AgentVote) -> AgentVoteLearningSnapshot:
    return AgentVoteLearningSnapshot(
        agent=vote.agent,
        signal=vote.signal,
        confidence=vote.confidence,
        weight=vote.weight,
        reasoning=vote.reasoning or [],
    )


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value

    return value.replace(tzinfo=timezone.utc)


def _exit_reason(trade: Trade) -> str | None:
    if trade.reconciliation_reason:
        return trade.reconciliation_reason
    if trade.decision and trade.decision.blocked_reason:
        return trade.decision.blocked_reason

    return None
