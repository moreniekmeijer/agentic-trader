from pathlib import Path
import asyncio
import logging
import os

from dotenv import load_dotenv

from agentic_trader.config.logging import setup_logging
from agentic_trader.database.session import create_tables
from agentic_trader.events.bus import EventBus
from agentic_trader.worker.context import build_worker_context
from agentic_trader.worker.registry import register_handlers
from agentic_trader.worker.scheduler import run_scheduler

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    load_dotenv(Path.home() / "Documents/secrets/agentic-trader/env")
    create_tables()

    logger.info("Starting agentic worker...")

    context = build_worker_context()
    bus = EventBus()
    register_handlers(bus, context)

    await bus.start()

    scheduler_task = asyncio.create_task(run_scheduler(bus, context))

    try:
        await scheduler_task
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await bus.stop()


if __name__ == "__main__":
    asyncio.run(main())
