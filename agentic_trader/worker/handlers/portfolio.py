import asyncio
import logging

from agentic_trader.broker.sync import sync_broker_snapshot
from agentic_trader.database.session import get_session
from agentic_trader.decision.engine import DecisionEngine
from agentic_trader.events.bus import EventBus
from agentic_trader.events.models import PositionReviewEvent, ReflectionTriggeredEvent
from agentic_trader.services.market_data.providers.yahoo_finance import YahooFinanceProvider
from agentic_trader.services.reflection.reflector_service import ReflectorService
from agentic_trader.worker.context import WorkerContext
from agentic_trader.worker.factories import build_portfolio_agent
from agentic_trader.services.execution.pnl_sync import FillPnLSync
from agentic_trader.services.portfolio.position_review import PositionReviewService

logger = logging.getLogger(__name__)


async def handle_reflection_triggered(
    event: ReflectionTriggeredEvent,
    bus: EventBus,
    context: WorkerContext,
) -> None:
    logger.info("Handling ReflectionTriggeredEvent...")

    def _reflect() -> None:
        with get_session() as session:
            FillPnLSync(session, context.alpaca_controller).run()
            service = ReflectorService(session, context.alpaca_controller)
            service.run_reflection_cycle()

    await asyncio.to_thread(_reflect)


async def handle_position_review(
    event: PositionReviewEvent,
    bus: EventBus,
    context: WorkerContext,
) -> None:
    logger.info("Handling PositionReviewEvent...")

    def _review() -> None:
        snapshot = sync_broker_snapshot(context.alpaca_controller)
        if snapshot is None:
            logger.error("Skipping position review because broker snapshot is unavailable")
            return

        if not snapshot.positions:
            logger.info("No open positions to review.")
            return

        provider = YahooFinanceProvider()
        portfolio_agent = build_portfolio_agent()

        with get_session() as session:
            decision_engine = DecisionEngine(
                context.alpaca_controller,
                context.risk_engine,
                session=session,
            )
            PositionReviewService(
                session=session,
                provider=provider,
                portfolio_agent=portfolio_agent,
                decision_engine=decision_engine,
            ).review_snapshot(snapshot)

    await asyncio.to_thread(_review)
