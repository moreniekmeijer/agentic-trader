from __future__ import annotations

import logging
from typing import Dict

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from agentic_trader.agents.technical.agent import TechnicalAgent
from agentic_trader.config.logging import setup_logging
from agentic_trader.controller.alpaca_controller import AlpacaController
from agentic_trader.data import sp500_symbols
from agentic_trader.decision.engine import DecisionEngine
from agentic_trader.risk.engine import RiskEngine
from agentic_trader.scanner.engine import ScannerEngine
from agentic_trader.services.market_data.feature_builder import FeatureBuilder
from agentic_trader.services.market_data.indicators.ma import MovingAverageIndicator
from agentic_trader.services.market_data.indicators.rsi import RSIIndicator
from agentic_trader.services.market_data.indicators.volume import VolumeIndicator
from agentic_trader.services.market_data.market_data_engine import MarketDataEngine
from agentic_trader.services.market_data.multi_timeframe_engine import MultiTimeframeEngine
from agentic_trader.services.market_data.providers.yahoo_finance import YahooFinanceProvider
from agentic_trader.worker.models import CACHE_MAX_AGE, TimeframeData
from agentic_trader.worker.scan_state import ScanState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SYMBOLS = sp500_symbols[:100]
SCAN_INTERVAL = 60  # minutes
TRADE_INTERVAL = 5  # minutes

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

state = ScanState()

# ---------------------------------------------------------------------------
# Pipeline factories
# ---------------------------------------------------------------------------

def build_scan_pipeline():
    """Lightweight pipeline used by the scanner (RSI + Volume only)."""
    provider = YahooFinanceProvider()
    engine = MarketDataEngine(indicators=[RSIIndicator(), VolumeIndicator()])
    features = FeatureBuilder()
    return provider, engine, features


def build_trade_pipeline() -> MultiTimeframeEngine:
    """Full pipeline used per trading cycle (RSI + MA50 + Volume)."""
    provider = YahooFinanceProvider()
    engine = MarketDataEngine(indicators=[RSIIndicator(), MovingAverageIndicator(50), VolumeIndicator()])
    features = FeatureBuilder()
    return MultiTimeframeEngine(provider, engine, features)

# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def scan_job() -> None:
    logger.info("Running scanner job")

    provider, engine, features = build_scan_pipeline()
    scanner = ScannerEngine(provider, engine, features)

    results = scanner.scan(SYMBOLS, top_number=10)

    if not results:
        logger.warning("Scanner returned no results, keeping previous shortlist")
        return

    top_symbols = [r.symbol for r in results]

    # Explicitly cache raw (uncomputed) df per symbol.
    # trade_job will apply its own wider indicator set on top of this raw data.
    raw_cache: Dict[str, TimeframeData] = {}
    for symbol in top_symbols:
        try:
            raw_cache[symbol] = TimeframeData(
                daily=provider.get_bars(symbol, interval="1d"),
                h4=provider.get_bars(symbol, interval="4h"),
            )
        except Exception as e:
            logger.warning(f"Failed to cache data for {symbol}: {e}")

    if not raw_cache:
        logger.warning("Could not cache any symbol data, skipping state update")
        return

    print(f"Cached {len(raw_cache)} symbols")

    valid_symbols = [s for s in top_symbols if s in raw_cache]
    state.update(symbols=valid_symbols, cache=raw_cache)


def trade_job() -> None:
    logger.info("Starting trading cycle")

    scan = state.get()

    if scan is None:
        logger.info("No scan results yet, skipping")
        return

    if not scan.is_fresh():
        logger.warning(f"Cache is stale (> {CACHE_MAX_AGE}), skipping trading")
        return

    controller = AlpacaController()
    risk_engine = RiskEngine(controller)
    decision_engine = DecisionEngine(controller, risk_engine)

    multi_engine = build_trade_pipeline()

    for symbol in scan.symbols:
        try:
            cached: TimeframeData | None = scan.cache.get(symbol)
            if cached is None:
                logger.warning(f"No cached data for {symbol}, skipping")
                continue

            multi_timeframe_snapshot = multi_engine.compute_from_cache(
                symbol=symbol,
                df_daily=cached.daily,
                df_4h=cached.h4,
            )

            agent = TechnicalAgent(symbol=symbol)
            response = agent.generate_signal(multi_timeframe_snapshot)

            if response.confidence < 0.2:
                logger.info(f"{symbol} skipped: confidence {response.confidence:.2f} below threshold")
                continue

            decision_engine.execute_decision(response)
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    setup_logging()
    load_dotenv()

    logger.info("Starting worker")

    # Prime the state before the scheduler takes over
    scan_job()
    trade_job()

    scheduler = BlockingScheduler()
    scheduler.add_job(scan_job, "interval", minutes=SCAN_INTERVAL)
    scheduler.add_job(trade_job, "interval", minutes=TRADE_INTERVAL)
    scheduler.start()
