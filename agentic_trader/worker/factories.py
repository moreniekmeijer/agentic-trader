from agentic_trader.agents.synthesizer.agent import SynthesizerAgent
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
