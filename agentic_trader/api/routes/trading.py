from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from agentic_trader.api.dependencies import get_db
from agentic_trader.api.schemas import (
    AgentVoteResponse,
    DecisionResponse,
    OrderIntentResponse,
    OrderIntentSubmissionResponse,
    TradeResponse,
)
from agentic_trader.controller.alpaca_controller import AlpacaController
from agentic_trader.database.models import Decision, OrderIntent, Trade
from agentic_trader.execution.controls import (
    broker_mode,
    broker_snapshot_max_age_seconds,
    broker_submissions_enabled,
)
from agentic_trader.execution.intent_submitter import (
    BrokerSnapshotStale,
    BrokerSubmissionsDisabled,
    IntentSubmissionFailed,
    IntentSubmitter,
)

router = APIRouter(tags=["trading"])


@router.get("/decisions", response_model=list[DecisionResponse])
def get_decisions(
    symbol: str | None = None,
    limit: int = Query(default=50, gt=0, le=500),
    session: Session = Depends(get_db),
) -> list[DecisionResponse]:
    query = session.query(Decision).options(joinedload(Decision.votes)).order_by(Decision.timestamp.desc())
    if symbol:
        query = query.filter(Decision.symbol == symbol.upper())

    return [_decision_response(decision) for decision in query.limit(limit).all()]


@router.get("/trades", response_model=list[TradeResponse])
def get_trades(
    symbol: str | None = None,
    limit: int = Query(default=50, gt=0, le=500),
    session: Session = Depends(get_db),
) -> list[TradeResponse]:
    query = session.query(Trade).order_by(Trade.timestamp.desc())
    if symbol:
        query = query.filter(Trade.symbol == symbol.upper())

    return [_trade_response(trade) for trade in query.limit(limit).all()]


@router.get("/order-intents", response_model=list[OrderIntentResponse])
def get_order_intents(
    status: str | None = None,
    symbol: str | None = None,
    limit: int = Query(default=100, gt=0, le=500),
    session: Session = Depends(get_db),
) -> list[OrderIntentResponse]:
    query = session.query(OrderIntent).order_by(OrderIntent.created_at.desc())
    if status:
        query = query.filter(OrderIntent.status == status)
    if symbol:
        query = query.filter(OrderIntent.symbol == symbol.upper())

    return [_intent_response(intent) for intent in query.limit(limit).all()]


@router.post(
    "/order-intents/{intent_id}/submit",
    response_model=OrderIntentSubmissionResponse,
)
def submit_order_intent(
    intent_id: int,
    session: Session = Depends(get_db),
) -> OrderIntentSubmissionResponse:
    intent = session.query(OrderIntent).filter_by(id=intent_id).first()
    if intent is None:
        raise HTTPException(status_code=404, detail="Order intent not found")
    if intent.status != "pending_approval":
        raise HTTPException(status_code=409, detail=f"Order intent is {intent.status}, not pending_approval")

    try:
        submitter = IntentSubmitter(
            session=session,
            alpaca_controller=AlpacaController(),
            snapshot_max_age_seconds=broker_snapshot_max_age_seconds(),
        )
        submitter.submit(intent)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BrokerSubmissionsDisabled as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BrokerSnapshotStale as exc:
        session.commit()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntentSubmissionFailed as exc:
        session.commit()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return OrderIntentSubmissionResponse(
        intent=_intent_response(intent),
    )


def _decision_response(decision: Decision) -> DecisionResponse:
    return DecisionResponse(
        id=decision.id,
        symbol=decision.symbol,
        timestamp=decision.timestamp,
        signal=decision.signal,
        confidence=decision.confidence,
        reasoning=decision.reasoning or [],
        executed=decision.executed,
        blocked_reason=decision.blocked_reason,
        thesis=decision.thesis,
        invalidation=decision.invalidation,
        expected_horizon_days=decision.expected_horizon_days,
        sector=decision.sector,
        setup_type=decision.setup_type,
        evidence=decision.evidence or [],
        market_snapshot=decision.market_snapshot,
        votes=[
            AgentVoteResponse(
                agent=vote.agent,
                signal=vote.signal,
                confidence=vote.confidence,
                weight=vote.weight,
                reasoning=vote.reasoning or [],
            )
            for vote in decision.votes
        ],
    )


def _trade_response(trade: Trade) -> TradeResponse:
    return TradeResponse(
        id=trade.id,
        symbol=trade.symbol,
        timestamp=trade.timestamp,
        side=trade.side,
        qty=trade.qty,
        price=trade.price,
        alpaca_order_id=trade.alpaca_order_id,
        closed_at=trade.closed_at,
        close_price=trade.close_price,
        pnl=trade.pnl,
        pnl_pct=trade.pnl_pct,
        needs_reconciliation=trade.needs_reconciliation,
        reconciliation_reason=trade.reconciliation_reason,
        decision_id=trade.decision_id,
    )


def _intent_response(intent: OrderIntent) -> OrderIntentResponse:
    return OrderIntentResponse(
        id=intent.id,
        created_at=intent.created_at,
        symbol=intent.symbol,
        side=intent.side,
        qty=intent.qty,
        order_type=intent.order_type,
        status=intent.status,
        rationale=intent.rationale,
        client_order_id=intent.client_order_id,
        submitted_at=intent.submitted_at,
        broker_order_id=intent.broker_order_id,
        error=intent.error,
        data=intent.data,
        broker_mode=broker_mode(),
        broker_submissions_enabled=broker_submissions_enabled(),
    )
