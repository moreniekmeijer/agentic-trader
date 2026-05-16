from agentic_trader.events.bus import EventBus
from agentic_trader.events.models import (
    BatchAnalysisRequestedEvent,
    FundamentalsRequestedEvent,
    PositionReviewEvent,
    ReflectionTriggeredEvent,
    ScanCompletedEvent,
    ScanTriggeredEvent,
    SymbolAnalysisRequestedEvent,
)
from agentic_trader.worker.context import WorkerContext
from agentic_trader.worker.handlers.analysis import handle_batch_analysis, handle_symbol_analysis
from agentic_trader.worker.handlers.portfolio import handle_position_review, handle_reflection_triggered
from agentic_trader.worker.handlers.scan import (
    handle_fundamentals_requested,
    handle_scan_completed,
    handle_scan_triggered,
)


def register_handlers(bus: EventBus, context: WorkerContext) -> None:
    bus.subscribe(ScanTriggeredEvent, lambda event: handle_scan_triggered(event, bus, context))
    bus.subscribe(ScanCompletedEvent, lambda event: handle_scan_completed(event, bus))
    bus.subscribe(FundamentalsRequestedEvent, lambda event: handle_fundamentals_requested(event, bus))
    bus.subscribe(SymbolAnalysisRequestedEvent, lambda event: handle_symbol_analysis(event, bus, context))
    bus.subscribe(BatchAnalysisRequestedEvent, lambda event: handle_batch_analysis(event, bus, context))
    bus.subscribe(PositionReviewEvent, lambda event: handle_position_review(event, bus, context))
    bus.subscribe(ReflectionTriggeredEvent, lambda event: handle_reflection_triggered(event, bus, context))
