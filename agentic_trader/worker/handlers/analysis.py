import asyncio
import logging

from agentic_trader.database.session import get_session
from agentic_trader.events.bus import EventBus
from agentic_trader.events.models import BatchAnalysisRequestedEvent, SymbolAnalysisRequestedEvent
from agentic_trader.services.arena import ArenaService
from agentic_trader.worker.context import WorkerContext

logger = logging.getLogger(__name__)


async def handle_symbol_analysis(
    event: SymbolAnalysisRequestedEvent,
    bus: EventBus,
    context: WorkerContext,
) -> None:
    logger.info("Analyzing %s...", event.symbol)

    def _analyze() -> None:
        with get_session() as session:
            service = ArenaService(
                session=session,
                alpaca_controller=context.alpaca_controller,
                risk_engine=context.risk_engine,
            )
            service.analyze_symbol(event.symbol)

    await asyncio.to_thread(_analyze)


async def handle_batch_analysis(
    event: BatchAnalysisRequestedEvent,
    bus: EventBus,
    context: WorkerContext,
) -> None:
    logger.info("Arena Mode: Analyzing batch of %d symbols...", len(event.symbols))

    def _analyze_all() -> None:
        with get_session() as session:
            service = ArenaService(
                session=session,
                alpaca_controller=context.alpaca_controller,
                risk_engine=context.risk_engine,
            )
            service.analyze_batch(event.symbols)

    await asyncio.to_thread(_analyze_all)
