import asyncio
import logging
from datetime import datetime, timezone

from agentic_trader.broker.sync import sync_broker_snapshot
from agentic_trader.database.repositories.market_state import MarketStateRepository
from agentic_trader.database.session import get_session
from agentic_trader.events.bus import EventBus
from agentic_trader.events.models import (
    BatchAnalysisRequestedEvent,
    PositionReviewEvent,
    ReflectionTriggeredEvent,
    ScanTriggeredEvent,
)
from agentic_trader.worker.context import WorkerContext

logger = logging.getLogger(__name__)


async def run_scheduler(bus: EventBus, context: WorkerContext) -> None:
    """Simple clock to emit events periodically."""
    logger.info("Scheduler started.")
    await asyncio.to_thread(sync_broker_snapshot, context.alpaca_controller)

    scan_timer = 0
    trade_timer = context.trade_interval_seconds

    await bus.publish(ScanTriggeredEvent(timestamp=datetime.now(timezone.utc)))
    await asyncio.sleep(5)

    while True:
        if scan_timer >= context.scan_interval_seconds:
            await bus.publish(ScanTriggeredEvent(timestamp=datetime.now(timezone.utc)))
            scan_timer = 0

        if trade_timer >= context.trade_interval_seconds:
            await _run_trading_cycle(bus, context)
            trade_timer = 0

        await asyncio.sleep(60)
        scan_timer += 60
        trade_timer += 60


async def _run_trading_cycle(bus: EventBus, context: WorkerContext) -> None:
    snapshot = await asyncio.to_thread(sync_broker_snapshot, context.alpaca_controller)
    if snapshot is None:
        logger.warning("Skipping trading cycle because broker snapshot is unavailable")
        return

    with get_session() as session:
        repo = MarketStateRepository(session)
        symbols = repo.get_active_shortlist()

    if symbols:
        await bus.publish(BatchAnalysisRequestedEvent(timestamp=datetime.now(timezone.utc), symbols=symbols))

    await bus.publish(PositionReviewEvent(timestamp=datetime.now(timezone.utc)))
    await bus.publish(ReflectionTriggeredEvent(timestamp=datetime.now(timezone.utc)))
