from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    """Base event class."""
    timestamp: datetime
    
    @property
    def name(self) -> str:
        return self.__class__.__name__


@dataclass
class ScanTriggeredEvent(Event):
    """Fired when a market scan should occur."""
    pass


@dataclass
class ScanCompletedEvent(Event):
    """Fired when a market scan completes."""
    symbols: list[str]


@dataclass
class FundamentalsRequestedEvent(Event):
    """Fired to fetch fundamentals for a specific symbol."""
    symbol: str


@dataclass
class SymbolAnalysisRequestedEvent(Event):
    """Fired when a symbol should be analyzed by the agents."""
    symbol: str

@dataclass
class BatchAnalysisRequestedEvent(Event):
    """Fired when multiple symbols should be analyzed in Arena Mode."""
    symbols: list[str]
    
@dataclass
class BracketOrderRequestedEvent(Event):
    """Fired when a bracket order is approved by the risk engine."""
    symbol: str
    signal: str
    qty: float
    entry_price: float
    stop_loss_price: float
    take_profit_price: float


@dataclass
class PositionReviewEvent(Event):
    """Fired daily to let the SynthesizerAgent review currently open positions."""
    pass

@dataclass
class ReflectionTriggeredEvent(Event):
    """Fired to scan for closed trades and generate AI reflections."""
    pass
