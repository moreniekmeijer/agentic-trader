import asyncio
import logging

from agentic_trader.agents.fundamental.agent import FundamentalsAgent
from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.agents.sentiment.agent import SentimentAgent
from agentic_trader.agents.technical.agent import TechnicalAgent
from agentic_trader.database.models import FundamentalsData
from agentic_trader.database.session import get_session
from agentic_trader.decision.engine import DecisionEngine
from agentic_trader.decision.portfolio_manager import PortfolioManager
from agentic_trader.events.bus import EventBus
from agentic_trader.events.models import BatchAnalysisRequestedEvent, SymbolAnalysisRequestedEvent
from agentic_trader.learning.journal import LearningJournal
from agentic_trader.scanner.models import CandidateReport
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

            learning = LearningJournal(session)
            past_lessons = learning.recent_lessons(event.symbol, limit=5)

            aggregated = discussion_engine.discuss(
                symbol=event.symbol,
                responses=votes,
                past_lessons=past_lessons,
            )
            aggregated = _attach_candidate_context(
                aggregated,
                CandidateReport(
                    symbol=event.symbol,
                    stage="sentiment_enriched",
                    market_snapshot=mtf_snapshot.model_dump(mode="json"),
                    agent_responses=votes,
                ),
            )
            portfolio_manager = PortfolioManager()
            aggregated = portfolio_manager.validate(
                aggregated,
                positions=context.alpaca_controller.get_positions(),
                open_orders=context.alpaca_controller.get_open_orders(),
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
        candidate_reports: dict[str, CandidateReport] = {}

        provider = YahooFinanceProvider()
        multi_engine = build_trade_pipeline()
        sentiment_agent = SentimentAgent()

        with get_session() as session:
            learning = LearningJournal(session)
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

                    try:
                        news = context.alpaca_controller.get_news(symbol, limit=5)
                        votes.append(sentiment_agent.generate_signal(symbol, news))
                    except Exception as exc:
                        logger.warning("Sentiment analysis skipped for %s: %s", symbol, exc)

                    symbol_reports[symbol] = votes
                    candidate_reports[symbol] = CandidateReport(
                        symbol=symbol,
                        stage="sentiment_enriched",
                        market_snapshot=mtf_snapshot.model_dump(mode="json"),
                        agent_responses=votes,
                    )

                    past_lessons_batch[symbol] = learning.recent_lessons(symbol, limit=3)
                except Exception as exc:
                    logger.warning("Skipping %s in batch due to error: %s", symbol, exc)

            if not symbol_reports:
                logger.warning("No symbols were successfully analyzed in batch.")
                return

            synthesizer = build_synthesizer_agent()
            decisions = synthesizer.discuss_batch(symbol_reports, past_lessons=past_lessons_batch)
            portfolio_manager = PortfolioManager()
            positions = context.alpaca_controller.get_positions()
            open_orders = context.alpaca_controller.get_open_orders()

            decision_engine = DecisionEngine(
                context.alpaca_controller,
                context.risk_engine,
                session=session,
            )
            for decision in decisions:
                report = candidate_reports.get(decision.symbol)
                if report is not None:
                    decision = _attach_candidate_context(decision, report)
                decision = portfolio_manager.validate(
                    decision,
                    positions=positions,
                    open_orders=open_orders,
                )
                decision_engine.execute_decision(decision)

    await asyncio.to_thread(_analyze_all)


def _attach_candidate_context(
    aggregated: AggregatedResponse,
    report: CandidateReport,
) -> AggregatedResponse:
    evidence = list(aggregated.evidence)
    for response in report.agent_responses:
        evidence.extend(response.reasoning)

    return aggregated.model_copy(
        update={
            "market_snapshot": report.market_snapshot,
            "evidence": evidence,
        }
    )
