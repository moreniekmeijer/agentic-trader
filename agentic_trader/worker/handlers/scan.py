import asyncio
import logging
from datetime import datetime, timedelta, timezone

from agentic_trader.database.repositories.market_state import MarketStateRepository
from agentic_trader.database.session import get_session
from agentic_trader.events.bus import EventBus
from agentic_trader.events.models import (
    FundamentalsRequestedEvent,
    ScanCompletedEvent,
    ScanTriggeredEvent,
)
from agentic_trader.scanner.engine import ScannerEngine
from agentic_trader.worker.context import WorkerContext
from agentic_trader.worker.factories import build_fundamentals_pipeline, build_scan_pipeline

logger = logging.getLogger(__name__)


async def handle_scan_triggered(event: ScanTriggeredEvent, bus: EventBus, context: WorkerContext) -> None:
    logger.info("Handling ScanTriggeredEvent...")

    def _scan():
        provider, engine, features = build_scan_pipeline()
        scanner = ScannerEngine(provider, engine, features)
        return scanner.scan(context.symbols, top_number=10)

    results = await asyncio.to_thread(_scan)

    if not results:
        logger.warning("Scanner returned no results.")
        return

    top_symbols = [r.symbol for r in results]
    logger.info("Scan complete - shortlist: %s", top_symbols)

    with get_session() as session:
        repo = MarketStateRepository(session)
        repo.set_active_shortlist(top_symbols)
        session.commit()

    await bus.publish(ScanCompletedEvent(timestamp=datetime.now(timezone.utc), symbols=top_symbols))


async def handle_scan_completed(event: ScanCompletedEvent, bus: EventBus) -> None:
    with get_session() as session:
        repo = MarketStateRepository(session)
        symbols_to_refresh = [
            symbol for symbol in event.symbols if repo.fundamentals_are_stale(symbol)
        ]

    for symbol in symbols_to_refresh:
        await bus.publish(FundamentalsRequestedEvent(timestamp=datetime.now(timezone.utc), symbol=symbol))


async def handle_fundamentals_requested(event: FundamentalsRequestedEvent, bus: EventBus) -> None:
    logger.info("Fetching fundamentals for %s...", event.symbol)

    def _fetch():
        engine = build_fundamentals_pipeline()
        return engine.fetch_many([event.symbol])

    snapshots = await asyncio.to_thread(_fetch)
    if not snapshots or event.symbol not in snapshots:
        logger.warning("No fundamentals found for %s", event.symbol)
        return

    snapshot = snapshots[event.symbol]

    with get_session() as session:
        repo = MarketStateRepository(session)
        repo.save_fundamentals(event.symbol, snapshot.model_dump(mode="json"))
        session.commit()

    logger.info("Saved fundamentals for %s.", event.symbol)



