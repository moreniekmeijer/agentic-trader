import asyncio
import logging
from collections import defaultdict
from typing import Callable, Coroutine, Type

from agentic_trader.events.models import Event

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Coroutine[None, None, None]]


class EventBus:
    """
    Asynchronous event bus for decoupling agentic workflows.
    """

    def __init__(self):
        self._subscribers: dict[Type[Event], list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

    def subscribe(self, event_type: Type[Event], handler: EventHandler) -> None:
        """Subscribe an async handler to a specific event type."""
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed {handler.__name__} to {event_type.__name__}")

    async def publish(self, event: Event) -> None:
        """Publish an event to the queue."""
        logger.info(f"Publishing event: {event.name}")
        await self._queue.put(event)

    async def start(self) -> None:
        """Start the event loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_events())
        logger.info("EventBus started")

    async def stop(self) -> None:
        """Stop processing events."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("EventBus stopped")

    async def _process_events(self) -> None:
        while self._running:
            try:
                event = await self._queue.get()
                handlers = self._subscribers.get(type(event), [])
                
                if not handlers:
                    logger.warning(f"No handlers found for event {event.name}")
                    self._queue.task_done()
                    continue

                for handler in handlers:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error(f"Error handling {event.name} in {handler.__name__}: {e}", exc_info=True)
                
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"EventBus error: {e}", exc_info=True)
