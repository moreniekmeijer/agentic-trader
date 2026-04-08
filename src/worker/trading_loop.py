import logging
from dotenv import load_dotenv

from apscheduler.schedulers.blocking import BlockingScheduler

from agents.technical.agent import TechnicalAgent
from config.logging import setup_logging
from decision.engine import DecisionEngine
from execution.alpaca_controller import AlpacaController
from providers.market_data.indicators.ma import MovingAverageIndicator
from providers.market_data.indicators.rsi import RSIIndicator
from providers.market_data.indicators.volume import VolumeIndicator
from providers.market_data.market_data_engine import MarketDataEngine
from providers.market_data.multi_timeframe_engine import MultiTimeframeEngine
from providers.market_data.providers.yahoo_finance import YahooFinanceProvider

logger = logging.getLogger(__name__)


SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "AVGO",
]
INTERVAL_MINUTES = 5


def build_pipeline(symbol):
    provider = YahooFinanceProvider()
    engine = MarketDataEngine(
        indicators=[RSIIndicator(), MovingAverageIndicator(50), VolumeIndicator()]
    )
    multi_engine = MultiTimeframeEngine(provider, engine)
    agent = TechnicalAgent(symbol=symbol)

    return multi_engine, agent


def run_cycle():
    logger.info("Starting trading cycle")

    alpaca = AlpacaController()
    decision_engine = DecisionEngine(alpaca)

    for symbol in SYMBOLS:
        try:
            logger.info(f"Processing symbol: {symbol}")

            multi_engine, agent = build_pipeline(symbol)

            snapshot = multi_engine.compute(symbol=symbol)
            response = agent.generate_signal(snapshot)

            logger.info(f"Agent response: {response}")

            # guard
            if response.confidence < 0.2:
                logger.info(f"Skipping {symbol} due to low confidence")
                continue

            trade_result = decision_engine.execute_decision(response)

            logger.info(f"Trade result: {trade_result}")

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}", exc_info=True)


if __name__ == "__main__":
    setup_logging()
    load_dotenv()

    logger.info("Starting trading worker")

    scheduler = BlockingScheduler()
    scheduler.add_job(run_cycle, "interval", minutes=INTERVAL_MINUTES)

    run_cycle()

    scheduler.start()
