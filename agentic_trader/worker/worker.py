import asyncio
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from agentic_trader.agents.fundamental.agent import FundamentalsAgent
from agentic_trader.agents.sentiment.agent import SentimentAgent
from agentic_trader.agents.synthesizer.agent import SynthesizerAgent
from agentic_trader.agents.technical.agent import TechnicalAgent
from agentic_trader.config.logging import setup_logging
from agentic_trader.controller.alpaca_controller import AlpacaController
from agentic_trader.data import sp500_symbols
from agentic_trader.database.models import FundamentalsData, MarketState, TradeJournal
from agentic_trader.database.session import create_tables, get_session
from agentic_trader.decision.engine import DecisionEngine
from agentic_trader.events.bus import EventBus
from agentic_trader.events.models import (
    FundamentalsRequestedEvent,
    ScanCompletedEvent,
    ScanTriggeredEvent,
    SymbolAnalysisRequestedEvent,
    BatchAnalysisRequestedEvent,
)
from agentic_trader.risk.engine import RiskEngine
from agentic_trader.scanner.engine import ScannerEngine
from agentic_trader.services.fundamentals.fundamentals_engine import FundamentalsEngine
from agentic_trader.services.fundamentals.providers.yahoo_finance import YahooFundamentalsProvider
from agentic_trader.services.market_data.feature_builder import FeatureBuilder
from agentic_trader.services.market_data.indicators.atr import ATRIndicator
from agentic_trader.services.market_data.indicators.ma import MovingAverageIndicator
from agentic_trader.services.market_data.indicators.rsi import RSIIndicator
from agentic_trader.services.market_data.indicators.volume import VolumeIndicator
from agentic_trader.services.market_data.market_data_engine import MarketDataEngine
from agentic_trader.services.market_data.multi_timeframe_engine import MultiTimeframeEngine
from agentic_trader.services.market_data.providers.yahoo_finance import YahooFinanceProvider
from agentic_trader.worker.models import TimeframeData

logger = logging.getLogger(__name__)

SYMBOLS = sp500_symbols[:10]
SCAN_INTERVAL = 24 * 60 * 60  # 24 hours
TRADE_INTERVAL = 24 * 60 * 60  # 24 hours

# Global instances (can be refactored into a DI container later)
alpaca_controller = AlpacaController()
risk_engine = RiskEngine(alpaca_controller)


def build_scan_pipeline():
    provider = YahooFinanceProvider()
    engine = MarketDataEngine(indicators=[RSIIndicator(), VolumeIndicator(), ATRIndicator()])
    features = FeatureBuilder()
    return provider, engine, features


def build_trade_pipeline() -> MultiTimeframeEngine:
    provider = YahooFinanceProvider()
    engine = MarketDataEngine(indicators=[RSIIndicator(), MovingAverageIndicator(50), VolumeIndicator()])
    features = FeatureBuilder()
    return MultiTimeframeEngine(provider, engine, features)


def build_fundamentals_pipeline() -> FundamentalsEngine:
    provider = YahooFundamentalsProvider()
    return FundamentalsEngine(provider)


def build_synthesizer_agent() -> SynthesizerAgent:
    return SynthesizerAgent(model="llama-3.3-70b-versatile")


def build_portfolio_agent():
    from agentic_trader.agents.portfolio.agent import PortfolioAgent
    return PortfolioAgent(model="llama-3.3-70b-versatile")


# ---------------------------------------------------------------------------
# Event Handlers
# ---------------------------------------------------------------------------

async def handle_scan_triggered(event: ScanTriggeredEvent, bus: EventBus) -> None:
    logger.info("Handling ScanTriggeredEvent...")
    # Run sync code in thread to avoid blocking loop
    def _scan():
        provider, engine, features = build_scan_pipeline()
        scanner = ScannerEngine(provider, engine, features)
        return scanner.scan(SYMBOLS, top_number=10)

    results = await asyncio.to_thread(_scan)

    if not results:
        logger.warning("Scanner returned no results.")
        return

    top_symbols = [r.symbol for r in results]
    logger.info(f"Scan complete — shortlist: {top_symbols}")

    with get_session() as session:
        state = session.query(MarketState).filter_by(key="active_shortlist").first()
        if not state:
            state = MarketState(key="active_shortlist", symbols=top_symbols)
            session.add(state)
        else:
            state.symbols = top_symbols
        session.commit()

    await bus.publish(ScanCompletedEvent(timestamp=datetime.now(timezone.utc), symbols=top_symbols))


async def handle_scan_completed(event: ScanCompletedEvent, bus: EventBus) -> None:
    for symbol in event.symbols:
        await bus.publish(FundamentalsRequestedEvent(timestamp=datetime.now(timezone.utc), symbol=symbol))


async def handle_fundamentals_requested(event: FundamentalsRequestedEvent, bus: EventBus) -> None:
    logger.info(f"Fetching fundamentals for {event.symbol}...")
    
    def _fetch():
        engine = build_fundamentals_pipeline()
        return engine.fetch_many([event.symbol])

    snapshots = await asyncio.to_thread(_fetch)
    if not snapshots or event.symbol not in snapshots:
        logger.warning(f"No fundamentals found for {event.symbol}")
        return

    snapshot = snapshots[event.symbol]
    
    with get_session() as session:
        fd = session.query(FundamentalsData).filter_by(symbol=event.symbol).first()
        if not fd:
            fd = FundamentalsData(symbol=event.symbol, data=snapshot.model_dump(mode="json"))
            session.add(fd)
        else:
            fd.data = snapshot.model_dump(mode="json")
        session.commit()
        
    logger.info(f"Saved fundamentals for {event.symbol}.")


async def handle_symbol_analysis(event: SymbolAnalysisRequestedEvent, bus: EventBus) -> None:
    logger.info(f"Analyzing {event.symbol}...")

    def _analyze():
        provider = YahooFinanceProvider()
        try:
            cached_market = TimeframeData(
                daily=provider.get_bars(event.symbol, interval="1d"),
                h4=provider.get_bars(event.symbol, interval="4h"),
            )
        except Exception as e:
            logger.warning(f"Failed to fetch market data for {event.symbol}: {e}")
            return

        with get_session() as session:
            fund_rec = session.query(FundamentalsData).filter_by(symbol=event.symbol).first()
            fund_data = fund_rec.data if fund_rec else None
            
            multi_engine = build_trade_pipeline()
            discussion_engine = build_synthesizer_agent()
            sentiment_agent = SentimentAgent()
            decision_engine = DecisionEngine(alpaca_controller, risk_engine, session=session)
            
            votes = []
            
            # 1. Technical Analysis
            mtf_snapshot = multi_engine.compute_from_cache(
                symbol=event.symbol,
                df_daily=cached_market.daily,
                df_4h=cached_market.h4,
            )
            votes.append(TechnicalAgent(symbol=event.symbol, buy_threshold=0.3, sell_threshold=0.3).generate_signal(mtf_snapshot))
            
            # 2. Fundamental Analysis
            if fund_data:
                from agentic_trader.services.fundamentals.models import FundamentalsSnapshot
                fs = FundamentalsSnapshot(**fund_data)
                votes.append(FundamentalsAgent(symbol=event.symbol, buy_threshold=0.3, sell_threshold=0.3).generate_signal(fs))
            
            # 3. Sentiment Analysis (New)
            try:
                news = alpaca_controller.get_news(event.symbol, limit=5)
                votes.append(sentiment_agent.generate_signal(event.symbol, news))
            except Exception as e:
                logger.warning(f"Sentiment analysis skipped for {event.symbol}: {e}")
            
            # Fetch past lessons
            journal_entries = session.query(TradeJournal).filter_by(symbol=event.symbol).order_by(TradeJournal.created_at.desc()).limit(5).all()
            past_lessons = [j.reflection for j in journal_entries]
            
            aggregated = discussion_engine.discuss(symbol=event.symbol, responses=votes, past_lessons=past_lessons)
            decision_engine.execute_decision(aggregated)

    await asyncio.to_thread(_analyze)


async def handle_batch_analysis(event: BatchAnalysisRequestedEvent, bus: EventBus) -> None:
    logger.info(f"Arena Mode: Analyzing batch of {len(event.symbols)} symbols...")

    def _analyze_all():
        symbol_reports = {}
        past_lessons_batch = {}
        
        provider = YahooFinanceProvider()
        multi_engine = build_trade_pipeline()
        sentiment_agent = SentimentAgent()
        
        with get_session() as session:
            for symbol in event.symbols:
                try:
                    # 1. Market Data
                    df_daily = provider.get_bars(symbol, interval="1d")
                    df_4h = provider.get_bars(symbol, interval="4h")
                    mtf_snapshot = multi_engine.compute_from_cache(symbol, df_daily=df_daily, df_4h=df_4h)
                    
                    # 2. Fundamentals
                    fund_rec = session.query(FundamentalsData).filter_by(symbol=symbol).first()
                    fund_data = fund_rec.data if fund_rec else None
                    
                    votes = []
                    # Technical
                    votes.append(TechnicalAgent(symbol=symbol, buy_threshold=0.3, sell_threshold=0.3).generate_signal(mtf_snapshot))
                    # Fundamentals
                    if fund_data:
                        from agentic_trader.services.fundamentals.models import FundamentalsSnapshot
                        votes.append(FundamentalsAgent(symbol=symbol, buy_threshold=0.3, sell_threshold=0.3).generate_signal(FundamentalsSnapshot(**fund_data)))
                    # Sentiment
                    news = alpaca_controller.get_news(symbol, limit=5)
                    votes.append(sentiment_agent.generate_signal(symbol, news))
                    
                    symbol_reports[symbol] = votes
                    
                    # Past lessons
                    journal_entries = session.query(TradeJournal).filter_by(symbol=symbol).order_by(TradeJournal.created_at.desc()).limit(3).all()
                    past_lessons_batch[symbol] = [j.reflection for j in journal_entries if j.reflection]
                    
                except Exception as e:
                    logger.warning(f"Skipping {symbol} in batch due to error: {e}")

            if not symbol_reports:
                logger.warning("No symbols were successfully analyzed in batch.")
                return

            # 3. Global Synthesis (The Arena)
            synthesizer = build_synthesizer_agent()
            decisions = synthesizer.discuss_batch(symbol_reports, past_lessons=past_lessons_batch)
            
            # 4. Execution
            decision_engine = DecisionEngine(alpaca_controller, risk_engine, session=session)
            for decision in decisions:
                decision_engine.execute_decision(decision)

    await asyncio.to_thread(_analyze_all)


async def handle_reflection_triggered(event, bus: EventBus) -> None:
    logger.info("Handling ReflectionTriggeredEvent...")
    
    def _reflect():
        from agentic_trader.services.reflection.reflector_service import ReflectorService
        with get_session() as session:
            service = ReflectorService(session, alpaca_controller)
            service.run_reflection_cycle()
            
    await asyncio.to_thread(_reflect)


async def handle_position_review(event, bus: EventBus) -> None:
    logger.info("Handling PositionReviewEvent...")
    
    def _review():
        try:
            positions = alpaca_controller.get_positions()
        except Exception as e:
            logger.error(f"Failed to fetch positions for review: {e}")
            return
            
        if not positions:
            logger.info("No open positions to review.")
            return
            
        provider = YahooFinanceProvider()
        portfolio_agent = build_portfolio_agent()
        
        with get_session() as session:
            decision_engine = DecisionEngine(alpaca_controller, risk_engine, session=session)
            
            from agentic_trader.database.models import Decision
            
            for pos in positions:
                symbol = pos.symbol
                current_price = float(pos.current_price)
                unrealized_pnl_pct = float(pos.unrealized_plpc)
                
                # Fetch ATR (requires fetching daily bars and running features)
                atr = None
                try:
                    df_daily = provider.get_bars(symbol, interval="1d")
                    df_4h = provider.get_bars(symbol, interval="4h")
                    engine = build_trade_pipeline()
                    mtf = engine.compute_from_cache(symbol, df_daily=df_daily, df_4h=df_4h)
                    atr = mtf.daily.atr if mtf and mtf.daily else None
                except Exception as e:
                    logger.warning(f"Could not fetch ATR for review of {symbol}: {e}")
                
                # Fetch original reasoning
                last_decision = session.query(Decision).filter_by(symbol=symbol, signal="BUY").order_by(Decision.timestamp.desc()).first()
                original_thesis = last_decision.reasoning if last_decision else []
                
                logger.info(f"Reviewing {symbol} | Price: {current_price} | PnL: {unrealized_pnl_pct:.2%}")
                
                decision = portfolio_agent.review_position(
                    symbol=symbol,
                    current_price=current_price,
                    unrealized_pnl_pct=unrealized_pnl_pct,
                    atr=atr,
                    original_thesis=original_thesis,
                )
                
                decision_engine.execute_review_decision(decision, symbol)
                
    await asyncio.to_thread(_review)


# ---------------------------------------------------------------------------
# Schedulers (Clock)
# ---------------------------------------------------------------------------

async def run_scheduler(bus: EventBus):
    """Simple clock to emit events periodically."""
    logger.info("Scheduler started.")
    
    scan_timer = 0
    trade_timer = TRADE_INTERVAL  # Set to interval so it fires immediately on first tick
    
    # Emit initial scan immediately
    await bus.publish(ScanTriggeredEvent(timestamp=datetime.now(timezone.utc)))
    
    # Give the initial scan 5 seconds to finish before the first tick
    await asyncio.sleep(5)
    
    while True:
        if scan_timer >= SCAN_INTERVAL:
            await bus.publish(ScanTriggeredEvent(timestamp=datetime.now(timezone.utc)))
            scan_timer = 0
            
        if trade_timer >= TRADE_INTERVAL:
            with get_session() as session:
                state = session.query(MarketState).filter_by(key="active_shortlist").first()
                symbols = state.symbols if state else []
            
            if symbols:
                await bus.publish(BatchAnalysisRequestedEvent(timestamp=datetime.now(timezone.utc), symbols=symbols))
            
            trade_timer = 0
            
            # Fire position review and reflection events
            from agentic_trader.events.models import PositionReviewEvent, ReflectionTriggeredEvent
            await bus.publish(PositionReviewEvent(timestamp=datetime.now(timezone.utc)))
            await bus.publish(ReflectionTriggeredEvent(timestamp=datetime.now(timezone.utc)))

        await asyncio.sleep(60)
        scan_timer += 60
        trade_timer += 60


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main():
    setup_logging()
    load_dotenv(os.getenv("ENV_FILE"))
    create_tables()

    logger.info("Starting agentic worker...")

    bus = EventBus()
    
    # Register handlers
    bus.subscribe(ScanTriggeredEvent, lambda e: handle_scan_triggered(e, bus))
    bus.subscribe(ScanCompletedEvent, lambda e: handle_scan_completed(e, bus))
    bus.subscribe(FundamentalsRequestedEvent, lambda e: handle_fundamentals_requested(e, bus))
    bus.subscribe(SymbolAnalysisRequestedEvent, lambda e: handle_symbol_analysis(e, bus))
    bus.subscribe(BatchAnalysisRequestedEvent, lambda e: handle_batch_analysis(e, bus))
    
    from agentic_trader.events.models import PositionReviewEvent, ReflectionTriggeredEvent
    bus.subscribe(PositionReviewEvent, lambda e: handle_position_review(e, bus))
    bus.subscribe(ReflectionTriggeredEvent, lambda e: handle_reflection_triggered(e, bus))

    await bus.start()
    
    scheduler_task = asyncio.create_task(run_scheduler(bus))
    
    try:
        await scheduler_task
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await bus.stop()

if __name__ == "__main__":
    asyncio.run(main())
