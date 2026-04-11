import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from agentic_trader.worker.models import ScanSnapshot, SymbolCache, TimeframeData

logger = logging.getLogger(__name__)


@dataclass
class ScanState:
    _snapshot: ScanSnapshot | None = field(default=None)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def update(self, symbols: List[str], cache: Dict[str, TimeframeData]) -> None:
        snapshot = ScanSnapshot(
            symbols=symbols,
            cache=SymbolCache(data=cache),
            timestamp=datetime.now(timezone.utc),
        )
        with self._lock:
            self._snapshot = snapshot

    def get(self) -> ScanSnapshot | None:
        with self._lock:
            return self._snapshot
