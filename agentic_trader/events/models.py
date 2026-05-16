from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Event(BaseModel):
    """Base event class."""

    timestamp: datetime = Field(default_factory=utcnow)

    @property
    def name(self) -> str:
        return self.__class__.__name__


class ScanTriggeredEvent(Event):
    """Fired when a market scan should occur."""

    pass


class ScanCompletedEvent(Event):
    """Fired when a market scan completes."""

    symbols: list[str]


class FundamentalsRequestedEvent(Event):
    """Fired to fetch fundamentals for a specific symbol."""

    symbol: str


class SymbolAnalysisRequestedEvent(Event):
    """Fired when a symbol should be analyzed by the agents."""

    symbol: str


class BatchAnalysisRequestedEvent(Event):
    """Fired when multiple symbols should be analyzed in Arena Mode."""

    symbols: list[str]


class BracketOrderRequestedEvent(Event):
    """Fired when a bracket order is approved by the risk engine."""

    symbol: str
    signal: str
    qty: float
    entry_price: float
    stop_loss_price: float
    take_profit_price: float


class PositionReviewEvent(Event):
    """Fired daily to let the SynthesizerAgent review currently open positions."""

    pass


class ReflectionTriggeredEvent(Event):
    """Fired to scan for closed trades and generate AI reflections."""

    pass
