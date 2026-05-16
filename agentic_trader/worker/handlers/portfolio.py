import asyncio
import logging

from agentic_trader.broker.sync import sync_broker_snapshot
from agentic_trader.database.models import Decision
from agentic_trader.database.session import get_session
from agentic_trader.decision.engine import DecisionEngine
from agentic_trader.events.bus import EventBus
from agentic_trader.events.models import PositionReviewEvent, ReflectionTriggeredEvent
from agentic_trader.services.market_data.providers.yahoo_finance import YahooFinanceProvider
from agentic_trader.services.reflection.reflector_service import ReflectorService
from agentic_trader.worker.context import WorkerContext
from agentic_trader.worker.factories import build_portfolio_agent, build_trade_pipeline

logger = logging.getLogger(__name__)


async def handle_reflection_triggered(
    event: ReflectionTriggeredEvent,
    bus: EventBus,
    context: WorkerContext,
) -> None:
    logger.info("Handling ReflectionTriggeredEvent...")

    def _reflect() -> None:
        with get_session() as session:
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

            for position in snapshot.positions:
                symbol = position.symbol
                current_price = float(position.current_price or 0.0)
                unrealized_pnl_pct = float(position.unrealized_plpc or 0.0)

                atr = None
                try:
                    df_daily = provider.get_bars(symbol, interval="1d")
                    df_4h = provider.get_bars(symbol, interval="4h")
                    engine = build_trade_pipeline()
                    mtf = engine.compute_from_cache(symbol, df_daily=df_daily, df_4h=df_4h)
                    atr = mtf.daily.atr if mtf and mtf.daily else None
                except Exception as exc:
                    logger.warning("Could not fetch ATR for review of %s: %s", symbol, exc)

                last_decision = (
                    session.query(Decision)
                    .filter_by(symbol=symbol, signal="BUY")
                    .order_by(Decision.timestamp.desc())
                    .first()
                )
                original_thesis = last_decision.reasoning if last_decision else []

                logger.info(
                    "Reviewing %s | Price: %s | PnL: %.2f%%",
                    symbol,
                    current_price,
                    unrealized_pnl_pct * 100,
                )

                decision = portfolio_agent.review_position(
                    symbol=symbol,
                    current_price=current_price,
                    unrealized_pnl_pct=unrealized_pnl_pct,
                    atr=atr,
                    original_thesis=original_thesis,
                )

                decision_engine.execute_review_decision(decision, symbol)

    await asyncio.to_thread(_review)
