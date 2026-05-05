from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session, joinedload

from agentic_trader.api.schemas import (
    AgentVoteResponse,
    DecisionResponse,
    TradeResponse,
    WatchlistCreate,
    WatchlistResponse,
    AgentPerformanceResponse,
)
from agentic_trader.config.logging import setup_logging
from agentic_trader.database.models import Decision, Trade, WatchlistEntry
from agentic_trader.database.repository import WatchlistRepository
from agentic_trader.database.session import SessionLocal, create_tables, drop_tables


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    load_dotenv(os.getenv("ENV_FILE"))

    # dev only
    # drop_tables()
    create_tables()

    yield

    # --- shutdown ---


app = FastAPI(
    title="Agentic Trader API",
    description="API for the Agentic Trader application",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# DB session
# ---------------------------------------------------------------------------


def get_db():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


# @app.get("/watchlist", response_model=list[WatchlistResponse])
# def get_watchlist(session: Session = Depends(get_db)):
#     entries = (
#         session.query(WatchlistEntry)
#         .filter(WatchlistEntry.is_active)
#         .order_by(WatchlistEntry.added_at.desc())
#         .all()
#     )
# 
#     return [
#         WatchlistResponse(
#             id=e.id,
#             symbol=e.symbol,
#             added_at=e.added_at,
#             added_by=e.added_by,
#             thesis=e.thesis,
#             invalidation=e.invalidation,
#             horizon=e.horizon,
#             review_after=e.review_after if e.review_after else None,
#         )
#         for e in entries
#     ]
# 
# 
# @app.post("/watchlist", response_model=WatchlistResponse)
# def add_to_watchlist(data: WatchlistCreate, session: Session = Depends(get_db)):
#     repo = WatchlistRepository(session)
# 
#     entry = repo.add(
#         symbol=data.symbol.upper(),
#         added_by=data.added_by or "manual",
#         thesis=data.thesis,
#         invalidation=data.invalidation,
#         horizon=data.horizon or "medium",
#         review_after=data.review_after,
#     )
# 
#     return WatchlistResponse(
#         id=entry.id,
#         symbol=entry.symbol,
#         added_at=entry.added_at,
#         added_by=entry.added_by,
#         thesis=entry.thesis,
#         invalidation=entry.invalidation,
#         horizon=entry.horizon,
#         review_after=entry.review_after if entry.review_after else None,
#     )
# 
# 
# @app.delete("/watchlist/{symbol}")
# def remove_from_watchlist(symbol: str, session: Session = Depends(get_db)):
#     repo = WatchlistRepository(session)
# 
#     before = repo.active_symbols()
#     repo.deactivate(symbol=symbol.upper(), reason="manual removal")
#     after = repo.active_symbols()
# 
#     if symbol.upper() in before and symbol.upper() not in after:
#         return {"status": "deactivated", "symbol": symbol.upper()}
# 
#     raise HTTPException(status_code=404, detail="Symbol not found")


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


@app.get("/decisions", response_model=list[DecisionResponse])
def get_decisions(symbol: str | None = None, limit: int = 50, session: Session = Depends(get_db)):
    query = session.query(Decision).options(joinedload(Decision.votes)).order_by(Decision.timestamp.desc())

    if symbol:
        query = query.filter(Decision.symbol == symbol.upper())

    decisions = query.limit(limit).all()

    return [
        DecisionResponse(
            id=d.id,
            symbol=d.symbol,
            timestamp=d.timestamp,
            signal=d.signal,
            confidence=d.confidence,
            reasoning=d.reasoning,
            executed=d.executed,
            blocked_reason=d.blocked_reason,
            votes=[
                AgentVoteResponse(
                    agent=v.agent,
                    signal=v.signal,
                    confidence=v.confidence,
                    weight=v.weight,
                    reasoning=v.reasoning,
                )
                for v in d.votes
            ],
        )
        for d in decisions
    ]


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------


@app.get("/trades", response_model=list[TradeResponse])
def get_trades(symbol: str | None = None, limit: int = 50, session: Session = Depends(get_db)):
    query = session.query(Trade).order_by(Trade.timestamp.desc())

    if symbol:
        query = query.filter(Trade.symbol == symbol.upper())

    trades = query.limit(limit).all()

    return [
        TradeResponse(
            id=t.id,
            symbol=t.symbol,
            timestamp=t.timestamp,
            side=t.side,
            qty=t.qty,
            price=t.price,
            alpaca_order_id=t.alpaca_order_id,
            closed_at=t.closed_at if t.closed_at else None,
            close_price=t.close_price,
            pnl=t.pnl,
            pnl_pct=t.pnl_pct,
            decision_id=t.decision_id,
        )
        for t in trades
    ]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


# @app.get("/analysis/agent-performance", response_model=list[AgentPerformanceResponse])
# def agent_performance(session: Session = Depends(get_db)):
#     results = (
#         session.query(
#             AgentVote.agent,
#             AgentVote.signal,
#             func.count().label("count"),
#             func.sum(Trade.pnl).label("total_pnl"),
#         )
#         .join(Decision, AgentVote.decision_id == Decision.id)
#         .join(Trade, Trade.decision_id == Decision.id)
#         .filter(Trade.pnl.isnot(None))
#         .group_by(AgentVote.agent, AgentVote.signal)
#         .all()
#     )
#
#     return [
#         AgentPerformanceResponse(
#             agent=r.agent,
#             signal=r.signal,
#             count=r.count,
#             total_pnl=float(r.total_pnl or 0.0),
#         )
#         for r in results
#     ]
