from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from agentic_trader.services.fundamentals.models import FundamentalsSnapshot
from agentic_trader.worker.models import (
    FundamentalsCache,
    ScanSnapshot,
    SymbolCache,
    TimeframeData,
)


@dataclass
class WorkerState:
    """
    Thread-safe shared state between scan_job, fundamentals_job and trade_job.
    """

    _scan: ScanSnapshot | None = field(default=None, init=False)
    _fundamentals: FundamentalsCache = field(default_factory=FundamentalsCache, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def update_market(self, symbols: List[str], cache: Dict[str, TimeframeData]) -> None:
        snapshot = ScanSnapshot(
            symbols=symbols,
            cache=SymbolCache(data=cache),
            timestamp=datetime.now(timezone.utc),
        )
        with self._lock:
            self._scan = snapshot

    def is_market_fresh(self) -> bool:
        with self._lock:
            if self._scan is None:
                return False
            return self._scan.is_fresh()

    def get_market(self, symbol: str) -> TimeframeData | None:
        with self._lock:
            if self._scan is None:
                return None
            return self._scan.cache.get(symbol)

    @property
    def symbols(self) -> List[str]:
        with self._lock:
            if self._scan is None:
                return []
            return list(self._scan.symbols)

    # ------------------------------------------------------------------
    # Fundamentals
    # ------------------------------------------------------------------

    def update_fundamentals(self, snapshots: Dict[str, FundamentalsSnapshot]) -> None:
        with self._lock:
            self._fundamentals.update(snapshots)

    def get_fundamentals(self, symbol: str) -> FundamentalsSnapshot | None:
        with self._lock:
            return self._fundamentals.get(symbol)

    def is_fundamentals_fresh(self, symbol: str) -> bool:
        with self._lock:
            return self._fundamentals.is_fresh(symbol)
