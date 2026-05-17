from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from agentic_trader.api.dependencies import get_db
from agentic_trader.learning import (
    AgentScorecard,
    DecisionLearningSnapshot,
    LearningJournal,
    LearningQuery,
    RejectedRecommendationSnapshot,
    TradeOutcomeSnapshot,
    compute_agent_scorecards,
)

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/decisions", response_model=list[DecisionLearningSnapshot])
def get_learning_decisions(
    symbol: str | None = None,
    sector: str | None = None,
    setup_type: str | None = None,
    agent: str | None = None,
    min_horizon_days: int | None = None,
    max_horizon_days: int | None = None,
    limit: int = Query(default=100, gt=0, le=500),
    session: Session = Depends(get_db),
) -> list[DecisionLearningSnapshot]:
    return LearningJournal(session).decision_contexts(
        _learning_query(symbol, sector, setup_type, agent, min_horizon_days, max_horizon_days, limit)
    )


@router.get("/rejected-recommendations", response_model=list[RejectedRecommendationSnapshot])
def get_rejected_recommendations(
    symbol: str | None = None,
    sector: str | None = None,
    setup_type: str | None = None,
    agent: str | None = None,
    min_horizon_days: int | None = None,
    max_horizon_days: int | None = None,
    limit: int = Query(default=100, gt=0, le=500),
    session: Session = Depends(get_db),
) -> list[RejectedRecommendationSnapshot]:
    return LearningJournal(session).rejected_recommendations(
        _learning_query(symbol, sector, setup_type, agent, min_horizon_days, max_horizon_days, limit)
    )


@router.get("/trade-outcomes", response_model=list[TradeOutcomeSnapshot])
def get_trade_outcomes(
    symbol: str | None = None,
    sector: str | None = None,
    setup_type: str | None = None,
    agent: str | None = None,
    min_horizon_days: int | None = None,
    max_horizon_days: int | None = None,
    limit: int = Query(default=100, gt=0, le=500),
    session: Session = Depends(get_db),
) -> list[TradeOutcomeSnapshot]:
    return LearningJournal(session).trade_outcomes(
        _learning_query(symbol, sector, setup_type, agent, min_horizon_days, max_horizon_days, limit)
    )


@router.get("/scorecards", response_model=list[AgentScorecard])
def get_agent_scorecards(
    symbol: str | None = None,
    limit: int | None = Query(default=None, gt=0, le=500),
    session: Session = Depends(get_db),
) -> list[AgentScorecard]:
    return compute_agent_scorecards(session, symbol=symbol, limit=limit)


def _learning_query(
    symbol: str | None,
    sector: str | None,
    setup_type: str | None,
    agent: str | None,
    min_horizon_days: int | None,
    max_horizon_days: int | None,
    limit: int,
) -> LearningQuery:
    return LearningQuery(
        symbol=symbol,
        sector=sector,
        setup_type=setup_type,
        agent=agent,
        min_horizon_days=min_horizon_days,
        max_horizon_days=max_horizon_days,
        limit=limit,
    )
