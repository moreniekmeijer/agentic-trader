from __future__ import annotations

import logging
from datetime import timedelta
from typing import Dict

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from agentic_trader.agents.discussion.agent import DiscussionAgent
from agentic_trader.agents.fundamental.agent import FundamentalsAgent
from agentic_trader.agents.technical.agent import TechnicalAgent
from agentic_trader.config.logging import setup_logging
from agentic_trader.controller.alpaca_controller import AlpacaController
from agentic_trader.data import sp500_symbols
from agentic_trader.decision.engine import DecisionEngine
from agentic_trader.risk.engine import RiskEngine
from agentic_trader.scanner.engine import ScannerEngine
from agentic_trader.services.fundamentals.fundamentals_engine import FundamentalsEngine
from agentic_trader.services.fundamentals.providers.yahoo_finance import YahooFundamentalsProvider
from agentic_trader.services.market_data.feature_builder import FeatureBuilder
from agentic_trader.services.market_data.indicators.ma import MovingAverageIndicator
from agentic_trader.services.market_data.indicators.rsi import RSIIndicator
from agentic_trader.services.market_data.indicators.volume import VolumeIndicator
from agentic_trader.services.market_data.market_data_engine import MarketDataEngine
from agentic_trader.services.market_data.multi_timeframe_engine import MultiTimeframeEngine
from agentic_trader.services.market_data.providers.yahoo_finance import YahooFinanceProvider
from agentic_trader.worker.models import CACHE_MAX_AGE, TimeframeData
from agentic_trader.worker.scan_state import WorkerState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SYMBOLS = sp500_symbols[:100]
SCAN_INTERVAL = 60      # minutes
TRADE_INTERVAL = 5      # minutes
FUNDAMENTALS_INTERVAL = 60  # minutes

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
    engine = MarketDataEngine(
        indicators=[RSIIndicator(), MovingAverageIndicator(50), VolumeIndicator()]
    )
    features = FeatureBuilder()
    return MultiTimeframeEngine(provider, engine, features)


def build_fundamentals_pipeline() -> FundamentalsEngine:
    """Fundamentals pipeline."""
    provider = YahooFundamentalsProvider()
    return FundamentalsEngine(provider)


def build_discussion_agent() -> DiscussionAgent:
    return DiscussionAgent(weights={
        "technical": 0.7,
        "fundamentals": 0.3,
    })

# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def scan_job() -> None:
    logger.info("Running scanner job...")

    provider, engine, features = build_scan_pipeline()
    scanner = ScannerEngine(provider, engine, features)

    results = scanner.scan(SYMBOLS, top_number=10)

    if not results:
        logger.warning("Scanner returned no results, keeping previous shortlist")
        return

    top_symbols = [r.symbol for r in results]

    market_cache: Dict[str, TimeframeData] = {}
    for symbol in top_symbols:
        try:
            market_cache[symbol] = TimeframeData(
                daily=provider.get_bars(symbol, interval="1d"),
                h4=provider.get_bars(symbol, interval="4h"),
            )
        except Exception as e:
            logger.warning(f"Failed to cache market data for {symbol}: {e}")

    if not market_cache:
        logger.warning("Could not cache any symbol data, skipping state update")
        return

    valid_symbols = [s for s in top_symbols if s in market_cache]
    state.update_market(symbols=valid_symbols, cache=market_cache)
    logger.info(f"Scan complete — shortlist: {valid_symbols}")


def fundamentals_job() -> None:
    logger.info("Running fundamentals job")

    symbols = state.symbols
    if not symbols:
        logger.info("No symbols in state yet, skipping fundamentals fetch")
        return

    engine = build_fundamentals_pipeline()
    snapshots = engine.fetch_many(symbols)

    if not snapshots:
        logger.warning("No fundamentals fetched, keeping previous cache")
        return

    state.update_fundamentals(snapshots)
    logger.info(f"Fundamentals updated for: {list(snapshots.keys())}")


def trade_job() -> None:
    logger.info("Starting trading cycle")

    if not state.is_market_fresh():
        logger.warning(f"Market cache is stale (> {CACHE_MAX_AGE}), skipping trading")
        return

    controller = AlpacaController()
    risk_engine = RiskEngine(controller)
    decision_engine = DecisionEngine(controller, risk_engine)
    multi_engine = build_trade_pipeline()
    discussion_engine = build_discussion_agent()

    for symbol in state.symbols:
        try:
            _trade_symbol(symbol, multi_engine, discussion_engine, decision_engine)
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}", exc_info=True)

# ---------------------------------------------------------------------------
# Per-symbol trade logic
# ---------------------------------------------------------------------------

def _trade_symbol(
    symbol: str,
    multi_engine: MultiTimeframeEngine,
    discussion_engine: DiscussionAgent,
    decision_engine: DecisionEngine,
) -> None:
    cached = state.get_market(symbol)
    if cached is None:
        logger.warning(f"{symbol}: no cached market data, skipping")
        return

    votes = []

    # --- Technical agent ---
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

    # --- Fundamentals agent ---
    fund_snapshot = state.get_fundamentals(symbol)
    if fund_snapshot is not None:
        votes.append(
            FundamentalsAgent(
                symbol=symbol,
                buy_threshold=0.3,
                sell_threshold=0.3,
            ).generate_signal(fund_snapshot))
    else:
        logger.debug(f"{symbol}: no fundamentals available, technical only")

    # --- Discussion ---
    aggregated = discussion_engine.discuss(symbol=symbol, responses=votes)

    # --- Decision + Risk + Execute ---
    decision_engine.execute_decision(aggregated)

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    setup_logging()
    load_dotenv()

    logger.info("Starting worker")

    scan_job()
    fundamentals_job()
    trade_job()

    scheduler = BlockingScheduler()
    scheduler.add_job(scan_job, "interval", minutes=SCAN_INTERVAL)
    scheduler.add_job(fundamentals_job, "interval", minutes=FUNDAMENTALS_INTERVAL)
    scheduler.add_job(trade_job, "interval", minutes=TRADE_INTERVAL)
    scheduler.start()