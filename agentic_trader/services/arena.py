import logging
from sqlalchemy.orm import Session

from agentic_trader.agents.fundamental.agent import FundamentalsAgent
from agentic_trader.agents.models import AggregatedResponse
from agentic_trader.agents.sentiment.agent import SentimentAgent
from agentic_trader.agents.technical.agent import TechnicalAgent
from agentic_trader.database.repositories.market_state import MarketStateRepository
from agentic_trader.decision.engine import DecisionEngine
from agentic_trader.decision.portfolio_manager import PortfolioManager
from agentic_trader.learning.journal import LearningJournal
from agentic_trader.scanner.models import CandidateReport
from agentic_trader.services.fundamentals.models import FundamentalsSnapshot
from agentic_trader.services.market_data.providers.yahoo_finance import YahooFinanceProvider
from agentic_trader.worker.factories import build_synthesizer_agent, build_trade_pipeline
from agentic_trader.worker.models import TimeframeData

logger = logging.getLogger(__name__)

class ArenaService:
    def __init__(self, session: Session, alpaca_controller, risk_engine):
        self.session = session
        self.alpaca_controller = alpaca_controller
        self.risk_engine = risk_engine

    def analyze_symbol(self, symbol: str) -> None:
        provider = YahooFinanceProvider()
        try:
            cached_market = TimeframeData(
                daily=provider.get_bars(symbol, interval="1d"),
                h4=provider.get_bars(symbol, interval="4h"),
            )
        except Exception as exc:
            logger.warning("Failed to fetch market data for %s: %s", symbol, exc)
            return

        repo = MarketStateRepository(self.session)
        fund_data = repo.get_fundamentals(symbol)

        multi_engine = build_trade_pipeline()
        discussion_engine = build_synthesizer_agent()
        sentiment_agent = SentimentAgent()
        decision_engine = DecisionEngine(
            self.alpaca_controller,
            self.risk_engine,
            session=self.session,
        )

        votes = []
        mtf_snapshot = multi_engine.compute_from_cache(
            symbol=symbol,
            df_daily=cached_market.daily,
            df_4h=cached_market.h4,
        )
        votes.append(
            TechnicalAgent(
                symbol=symbol,
                buy_threshold=0.3,
                sell_threshold=0.3,
            ).generate_signal(mtf_snapshot)
        )

        if fund_data:
            votes.append(
                FundamentalsAgent(
                    symbol=symbol,
                    buy_threshold=0.3,
                    sell_threshold=0.3,
                ).generate_signal(FundamentalsSnapshot(**fund_data))
            )

        try:
            news = self.alpaca_controller.get_news(symbol, limit=5)
            votes.append(sentiment_agent.generate_signal(symbol, news))
        except Exception as exc:
            logger.warning("Sentiment analysis skipped for %s: %s", symbol, exc)

        learning = LearningJournal(self.session)
        past_lessons = learning.recent_lessons(symbol, limit=5)

        aggregated = discussion_engine.discuss(
            symbol=symbol,
            responses=votes,
            past_lessons=past_lessons,
        )
        aggregated = self._attach_candidate_context(
            aggregated,
            CandidateReport(
                symbol=symbol,
                stage="sentiment_enriched",
                market_snapshot=mtf_snapshot.model_dump(mode="json"),
                agent_responses=votes,
            ),
        )
        portfolio_manager = PortfolioManager()
        aggregated = portfolio_manager.validate(aggregated)
        decision_engine.execute_decision(aggregated)

    def analyze_batch(self, symbols: list[str]) -> None:
        symbol_reports = {}
        past_lessons_batch = {}
        candidate_reports: dict[str, CandidateReport] = {}

        provider = YahooFinanceProvider()
        multi_engine = build_trade_pipeline()
        sentiment_agent = SentimentAgent()

        learning = LearningJournal(self.session)
        for symbol in symbols:
            try:
                df_daily = provider.get_bars(symbol, interval="1d")
                df_4h = provider.get_bars(symbol, interval="4h")
                mtf_snapshot = multi_engine.compute_from_cache(
                    symbol,
                    df_daily=df_daily,
                    df_4h=df_4h,
                )

                repo = MarketStateRepository(self.session)
                fund_data = repo.get_fundamentals(symbol)

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
                    news = self.alpaca_controller.get_news(symbol, limit=5)
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

        decision_engine = DecisionEngine(
            self.alpaca_controller,
            self.risk_engine,
            session=self.session,
        )
        for decision in decisions:
            report = candidate_reports.get(decision.symbol)
            if report is not None:
                decision = self._attach_candidate_context(decision, report)
            decision = portfolio_manager.validate(decision)
            decision_engine.execute_decision(decision)

    def _attach_candidate_context(
        self,
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
