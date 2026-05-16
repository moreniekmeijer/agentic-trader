import asyncio
import logging

from agentic_trader.agents.fundamental.agent import FundamentalsAgent
from agentic_trader.agents.sentiment.agent import SentimentAgent
from agentic_trader.agents.technical.agent import TechnicalAgent
from agentic_trader.database.models import FundamentalsData, TradeJournal
from agentic_trader.database.session import get_session
from agentic_trader.decision.engine import DecisionEngine
from agentic_trader.events.bus import EventBus
from agentic_trader.events.models import BatchAnalysisRequestedEvent, SymbolAnalysisRequestedEvent
from agentic_trader.services.fundamentals.models import FundamentalsSnapshot
from agentic_trader.services.market_data.providers.yahoo_finance import YahooFinanceProvider
from agentic_trader.worker.context import WorkerContext
from agentic_trader.worker.factories import build_synthesizer_agent, build_trade_pipeline
from agentic_trader.worker.models import TimeframeData

logger = logging.getLogger(__name__)


async def handle_symbol_analysis(
    event: SymbolAnalysisRequestedEvent,
    bus: EventBus,
    context: WorkerContext,
) -> None:
    logger.info("Analyzing %s...", event.symbol)

    def _analyze() -> None:
        provider = YahooFinanceProvider()
        try:
            cached_market = TimeframeData(
                daily=provider.get_bars(event.symbol, interval="1d"),
                h4=provider.get_bars(event.symbol, interval="4h"),
            )
        except Exception as exc:
            logger.warning("Failed to fetch market data for %s: %s", event.symbol, exc)
            return

        with get_session() as session:
            fund_rec = session.query(FundamentalsData).filter_by(symbol=event.symbol).first()
            fund_data = fund_rec.data if fund_rec else None

            multi_engine = build_trade_pipeline()
            discussion_engine = build_synthesizer_agent()
            sentiment_agent = SentimentAgent()
            decision_engine = DecisionEngine(
                context.alpaca_controller,
                context.risk_engine,
                session=session,
            )

            votes = []
            mtf_snapshot = multi_engine.compute_from_cache(
                symbol=event.symbol,
                df_daily=cached_market.daily,
                df_4h=cached_market.h4,
            )
            votes.append(
                TechnicalAgent(
                    symbol=event.symbol,
                    buy_threshold=0.3,
                    sell_threshold=0.3,
                ).generate_signal(mtf_snapshot)
            )

            if fund_data:
                votes.append(
                    FundamentalsAgent(
                        symbol=event.symbol,
                        buy_threshold=0.3,
                        sell_threshold=0.3,
                    ).generate_signal(FundamentalsSnapshot(**fund_data))
                )

            try:
                news = context.alpaca_controller.get_news(event.symbol, limit=5)
                votes.append(sentiment_agent.generate_signal(event.symbol, news))
            except Exception as exc:
                logger.warning("Sentiment analysis skipped for %s: %s", event.symbol, exc)

            journal_entries = (
                session.query(TradeJournal)
                .filter_by(symbol=event.symbol)
                .order_by(TradeJournal.created_at.desc())
                .limit(5)
                .all()
            )
            past_lessons = [entry.reflection for entry in journal_entries]

            aggregated = discussion_engine.discuss(
                symbol=event.symbol,
                responses=votes,
                past_lessons=past_lessons,
            )
            decision_engine.execute_decision(aggregated)

    await asyncio.to_thread(_analyze)


async def handle_batch_analysis(
    event: BatchAnalysisRequestedEvent,
    bus: EventBus,
    context: WorkerContext,
) -> None:
    logger.info("Arena Mode: Analyzing batch of %d symbols...", len(event.symbols))

    def _analyze_all() -> None:
        symbol_reports = {}
        past_lessons_batch = {}

        provider = YahooFinanceProvider()
        multi_engine = build_trade_pipeline()
        sentiment_agent = SentimentAgent()

        with get_session() as session:
            for symbol in event.symbols:
                try:
                    df_daily = provider.get_bars(symbol, interval="1d")
                    df_4h = provider.get_bars(symbol, interval="4h")
                    mtf_snapshot = multi_engine.compute_from_cache(
                        symbol,
                        df_daily=df_daily,
                        df_4h=df_4h,
                    )

                    fund_rec = session.query(FundamentalsData).filter_by(symbol=symbol).first()
                    fund_data = fund_rec.data if fund_rec else None

                    votes = [
                        TechnicalAgent(
                            symbol=symbol,
                            buy_threshold=0.3,
                            sell_threshold=0.3,
                        ).generate_signal(mtf_snapshot)
                    ]
                    if fund_data:
                        votes.append(
                            FundamentalsAgent(
                                symbol=symbol,
                                buy_threshold=0.3,
                                sell_threshold=0.3,
                            ).generate_signal(FundamentalsSnapshot(**fund_data))
                        )

                    news = context.alpaca_controller.get_news(symbol, limit=5)
                    votes.append(sentiment_agent.generate_signal(symbol, news))

                    symbol_reports[symbol] = votes

                    journal_entries = (
                        session.query(TradeJournal)
                        .filter_by(symbol=symbol)
                        .order_by(TradeJournal.created_at.desc())
                        .limit(3)
                        .all()
                    )
                    past_lessons_batch[symbol] = [
                        entry.reflection for entry in journal_entries if entry.reflection
                    ]
                except Exception as exc:
                    logger.warning("Skipping %s in batch due to error: %s", symbol, exc)

            if not symbol_reports:
                logger.warning("No symbols were successfully analyzed in batch.")
                return

            synthesizer = build_synthesizer_agent()
            decisions = synthesizer.discuss_batch(symbol_reports, past_lessons=past_lessons_batch)

            decision_engine = DecisionEngine(
                context.alpaca_controller,
                context.risk_engine,
                session=session,
            )
            for decision in decisions:
                decision_engine.execute_decision(decision)

    await asyncio.to_thread(_analyze_all)
