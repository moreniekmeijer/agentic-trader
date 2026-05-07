from __future__ import annotations

import logging
import os
from typing import Dict

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from agentic_trader.agents.discussion.agent import DiscussionAgent
from agentic_trader.agents.fundamental.agent import FundamentalsAgent
from agentic_trader.agents.models import AgentResponse
from agentic_trader.agents.sentiment.agent import SentimentAgent
from agentic_trader.agents.technical.agent import TechnicalAgent
from agentic_trader.config.logging import setup_logging
from agentic_trader.controller.alpaca_controller import AlpacaController
from agentic_trader.data import sp500_symbols
from agentic_trader.database.session import get_session
from agentic_trader.decision.engine import DecisionEngine
from agentic_trader.risk.engine import RiskEngine
from agentic_trader.scanner.engine import ScannerEngine
from agentic_trader.scanner.models import CandidateContext
from agentic_trader.services.fundamentals.fundamentals_engine import FundamentalsEngine
from agentic_trader.services.fundamentals.providers.yahoo_finance import YahooFundamentalsProvider
from agentic_trader.services.market_data.feature_builder import FeatureBuilder
from agentic_trader.services.market_data.indicators.ma import MovingAverageIndicator
from agentic_trader.services.market_data.indicators.rsi import RSIIndicator
from agentic_trader.services.market_data.indicators.volume import VolumeIndicator
from agentic_trader.services.market_data.market_data_engine import MarketDataEngine
from agentic_trader.services.market_data.multi_timeframe_engine import MultiTimeframeEngine
from agentic_trader.services.market_data.providers.yahoo_finance import YahooFinanceProvider
from agentic_trader.services.market_data.response import MultiTimeframeSnapshot
from agentic_trader.services.sentiment.providers.null import NullSentimentProvider
from agentic_trader.services.sentiment.sentiment_engine import SentimentEngine
from agentic_trader.worker.models import CACHE_MAX_AGE, TimeframeData
from agentic_trader.worker.pnl_sync import PnlSyncJob
from agentic_trader.worker.reconciliation import ReconciliationJob
from agentic_trader.worker.scan_state import WorkerState

logger = logging.getLogger(__name__)
load_dotenv(os.getenv("ENV_FILE"))

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _env_int(
    name: str,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning(f"Invalid integer for {name}={raw!r}; using {default}")
        return default
    if min_value is not None and value < min_value:
        logger.warning(f"{name}={value} is below minimum {min_value}; using {default}")
        return default
    if max_value is not None and value > max_value:
        logger.warning(f"{name}={value} is above maximum {max_value}; using {default}")
        return default
    return value


QUALITY_UNIVERSE_SIZE = _env_int("QUALITY_UNIVERSE_SIZE", 30, min_value=1, max_value=len(sp500_symbols))
ACTIVE_SHORTLIST_SIZE = _env_int("ACTIVE_SHORTLIST_SIZE", 10, min_value=1, max_value=len(sp500_symbols))
SCAN_UNIVERSE_LIMIT = _env_int("SCAN_UNIVERSE_LIMIT", 0, min_value=0, max_value=len(sp500_symbols))
SCAN_INTERVAL = _env_int("TECHNICAL_SCAN_INTERVAL", 24 * 60, min_value=1)  # minutes
TRADE_INTERVAL = _env_int("TRADE_INTERVAL", 5, min_value=1)  # minutes
FUNDAMENTALS_INTERVAL = _env_int("FUNDAMENTALS_INTERVAL", 7 * 24 * 60, min_value=1)  # minutes
SENTIMENT_INTERVAL = _env_int("SENTIMENT_INTERVAL", 60, min_value=1)  # minutes
PNL_SYNC_INTERVAL = _env_int("PNL_SYNC_INTERVAL", 5, min_value=1)  # minutes
RECONCILIATION_INTERVAL = _env_int("RECONCILIATION_INTERVAL", 10, min_value=1)  # minutes

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

state = WorkerState()

# ---------------------------------------------------------------------------
# Pipeline factories
# ---------------------------------------------------------------------------


def build_scan_pipeline():
    """Lightweight pipeline: RSI + Volume."""
    provider = YahooFinanceProvider()
    engine = MarketDataEngine(indicators=[RSIIndicator(), VolumeIndicator()])
    features = FeatureBuilder()
    return provider, engine, features


def build_trade_pipeline() -> MultiTimeframeEngine:
    """Full pipeline: RSI + MA50 + Volume."""
    provider = YahooFinanceProvider()
    engine = MarketDataEngine(indicators=[RSIIndicator(), MovingAverageIndicator(50), VolumeIndicator()])
    features = FeatureBuilder()
    return MultiTimeframeEngine(provider, engine, features)


def build_fundamentals_pipeline() -> FundamentalsEngine:
    """Fundamentals pipeline."""
    provider = YahooFundamentalsProvider()
    return FundamentalsEngine(provider)


def build_sentiment_pipeline() -> SentimentEngine:
    """Sentiment pipeline."""
    provider = NullSentimentProvider()
    return SentimentEngine(provider)


def build_discussion_agent() -> DiscussionAgent:
    return DiscussionAgent(
        weights={
            "technical": 0.6,
            "fundamentals": 0.3,
            "sentiment": 0.1,
        }
    )


def _source_symbols() -> list[str]:
    symbols = list(dict.fromkeys(sp500_symbols))
    if SCAN_UNIVERSE_LIMIT > 0:
        return symbols[:SCAN_UNIVERSE_LIMIT]
    return symbols


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


def _is_usable_frame(frame) -> bool:
    return frame is not None and not frame.empty and len(frame) >= 2


def _has_usable_timeframe_data(data: TimeframeData) -> bool:
    return _is_usable_frame(data.daily) and _is_usable_frame(data.h4)


def _responses_without_agent(responses: list[AgentResponse], agent: str) -> list[AgentResponse]:
    return [response for response in responses if response.agent != agent]


def _dedupe_responses(responses: list[AgentResponse]) -> list[AgentResponse]:
    by_agent = {}
    for response in responses:
        by_agent[response.agent] = response
    return list(by_agent.values())


def _reasons_from_responses(responses: list[AgentResponse]) -> list[str]:
    return [reason for response in responses for reason in response.reasoning]


def _has_response(responses: list[AgentResponse], agent: str) -> bool:
    return any(response.agent == agent for response in responses)


def quality_universe_job() -> None:
    logger.info("Running fundamentals quality-universe job")

    symbols = _source_symbols()
    engine = build_fundamentals_pipeline()
    snapshots = engine.fetch_many(symbols)

    if not snapshots:
        logger.warning("No fundamentals fetched, keeping previous quality universe")
        return

    state.update_fundamentals(snapshots)

    provider, market_engine, features = build_scan_pipeline()
    scanner = ScannerEngine(provider, market_engine, features)
    candidates = scanner.build_quality_universe(snapshots, top_number=QUALITY_UNIVERSE_SIZE)

    if not candidates:
        logger.warning("No quality candidates built, keeping previous quality universe")
        return

    state.update_quality_universe(candidates)
    logger.info(
        f"Quality universe updated — top {len(candidates)}: {[candidate.symbol for candidate in candidates]}"
    )


def scan_job() -> None:
    logger.info("Running technical shortlist job")

    quality_candidates = state.quality_universe
    if not quality_candidates:
        logger.info("No quality universe available yet, skipping technical shortlist")
        return

    multi_engine = build_trade_pipeline()
    scanner = ScannerEngine(multi_engine.provider, multi_engine.engine, multi_engine.features)
    market_cache: Dict[str, TimeframeData] = {}
    market_snapshots: dict[str, MultiTimeframeSnapshot] = {}

    for candidate in quality_candidates:
        symbol = candidate.symbol
        try:
            timeframe_data = TimeframeData(
                daily=multi_engine.provider.get_bars(symbol, interval="1d"),
                h4=multi_engine.provider.get_bars(symbol, interval="4h"),
            )
            if not _has_usable_timeframe_data(timeframe_data):
                logger.warning(f"Skipping {symbol}: incomplete market data for one or more timeframes")
                continue
            market_cache[symbol] = timeframe_data
            market_snapshots[symbol] = multi_engine.compute_from_cache(
                symbol=symbol,
                df_daily=timeframe_data.daily,
                df_4h=timeframe_data.h4,
            )
        except Exception as e:
            logger.warning(f"Failed to cache market data for {symbol}: {e}")

    if not market_cache:
        logger.warning("Could not cache any symbol data, skipping state update")
        return

    shortlist = scanner.build_active_shortlist(
        quality_candidates,
        market_snapshots,
        top_number=ACTIVE_SHORTLIST_SIZE,
    )
    if not shortlist:
        logger.warning("Technical shortlist returned no long candidates, keeping previous shortlist")
        return

    state.update_active_shortlist(candidates=shortlist, cache=market_cache)
    with get_session() as session:
        state.persist_to_db(session)
    logger.info(
        f"Technical shortlist complete — active shortlist: {[candidate.symbol for candidate in shortlist]}"
    )


def fundamentals_job() -> None:
    quality_universe_job()


def sentiment_job() -> None:
    logger.info("Running sentiment enrichment job")

    shortlist = state.active_shortlist
    if not shortlist:
        logger.info("No active shortlist available yet, skipping sentiment enrichment")
        return

    engine = build_sentiment_pipeline()
    symbols = [candidate.symbol for candidate in shortlist]
    snapshots = engine.fetch_many(symbols)
    if not snapshots:
        logger.warning("No sentiment snapshots fetched, keeping previous shortlist enrichment")
        return

    enriched: list[CandidateContext] = []
    for candidate in shortlist:
        snapshot = snapshots.get(candidate.symbol)
        if snapshot is None:
            enriched.append(candidate)
            continue

        response = SentimentAgent(
            symbol=candidate.symbol,
            buy_threshold=0.3,
            sell_threshold=0.3,
        ).generate_signal(snapshot)
        base_responses = _responses_without_agent(candidate.evaluator_responses, "sentiment")
        responses = [*base_responses, response]
        enriched.append(
            candidate.model_copy(
                update={
                    "stage": "sentiment_enriched",
                    "sentiment_score": round(snapshot.score * snapshot.confidence, 3),
                    "evaluator_responses": responses,
                    "reasons": _reasons_from_responses(responses),
                    "updated_at": snapshot.fetched_at,
                }
            )
        )

    state.update_sentiment(enriched)
    logger.info(f"Sentiment enrichment complete — enriched: {[candidate.symbol for candidate in enriched]}")


def trade_job() -> None:
    logger.info("Starting trading cycle")

    if not state.is_market_fresh():
        logger.warning(f"Market cache is stale (> {CACHE_MAX_AGE}), skipping trading")
        return

    controller = AlpacaController()
    risk_engine = RiskEngine(controller)
    multi_engine = build_trade_pipeline()
    discussion_engine = build_discussion_agent()

    for symbol in state.symbols:
        try:
            with get_session() as session:
                decision_engine = DecisionEngine(controller, risk_engine, session=session)
                _trade_symbol(symbol, multi_engine, discussion_engine, decision_engine)
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}", exc_info=True)

    with get_session() as session:
        state.persist_to_db(session)


# ---------------------------------------------------------------------------
# Per-symbol trade logic
# ---------------------------------------------------------------------------


def _trade_symbol(
    symbol: str,
    multi_engine: MultiTimeframeEngine,
    discussion_engine: DiscussionAgent,
    decision_engine: DecisionEngine,
) -> None:
    candidate = state.get_candidate(symbol)
    cached = state.get_market(symbol)
    if cached is None:
        logger.warning(f"{symbol}: no cached market data, skipping")
        return
    if not _has_usable_timeframe_data(cached):
        logger.warning(f"{symbol}: cached market data is incomplete, skipping")
        return

    votes = _dedupe_responses(candidate.evaluator_responses) if candidate is not None else []

    # Candidate context is the preferred path. Fallbacks keep the worker
    # resilient if it resumes from only heartbeat symbols after a restart.
    if not _has_response(votes, "technical"):
        mtf_snapshot = candidate.market if candidate is not None else None
        if mtf_snapshot is None:
            mtf_snapshot = multi_engine.compute_from_cache(
                symbol=symbol,
                df_daily=cached.daily,
                df_4h=cached.h4,
            )
        votes.append(
            TechnicalAgent(
                symbol=symbol,
                buy_threshold=0.3,
                sell_threshold=0.3,
            ).generate_signal(mtf_snapshot)
        )

    if not _has_response(votes, "fundamentals"):
        fund_snapshot = candidate.fundamentals if candidate is not None else None
        if fund_snapshot is None:
            fund_snapshot = state.get_fundamentals(symbol)
        if fund_snapshot is not None:
            votes.append(
                FundamentalsAgent(
                    symbol=symbol,
                    buy_threshold=0.3,
                    sell_threshold=0.3,
                ).generate_signal(fund_snapshot)
            )
        else:
            logger.debug(f"{symbol}: no fundamentals available, technical only")

    if not votes:
        logger.warning(f"{symbol}: no scanner/evaluator responses available, skipping")
        return

    # --- Discussion ---
    aggregated = discussion_engine.discuss(symbol=symbol, responses=votes)

    # --- Decision + Risk + Execute ---
    decision_engine.execute_decision(aggregated)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    setup_logging()
    load_dotenv(os.getenv("ENV_FILE"))

    logger.info("Starting worker")
    with get_session() as session:
        restored = state.load_from_db(session)
    if restored:
        logger.info(f"Restored {len(restored)} symbols from heartbeat state")

    quality_universe_job()
    scan_job()
    sentiment_job()
    trade_job()
    pnl_sync = PnlSyncJob(AlpacaController())
    reconciliation = ReconciliationJob(AlpacaController())

    scheduler = BlockingScheduler()
    scheduler.add_job(quality_universe_job, "interval", minutes=FUNDAMENTALS_INTERVAL)
    scheduler.add_job(scan_job, "interval", minutes=SCAN_INTERVAL)
    scheduler.add_job(sentiment_job, "interval", minutes=SENTIMENT_INTERVAL)
    scheduler.add_job(trade_job, "interval", minutes=TRADE_INTERVAL)
    scheduler.add_job(pnl_sync.run, "interval", minutes=PNL_SYNC_INTERVAL)
    scheduler.add_job(reconciliation.run, "interval", minutes=RECONCILIATION_INTERVAL)
    scheduler.start()
