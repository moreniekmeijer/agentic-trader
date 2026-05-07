from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from agentic_trader.database.repository import SystemRepository
from agentic_trader.scanner.models import CandidateContext, ScannerStageSnapshot
from agentic_trader.services.fundamentals.models import FundamentalsSnapshot
from agentic_trader.worker.models import (
    FundamentalsCache,
    ScannerPipelineState,
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
    _scanner: ScannerPipelineState = field(default_factory=ScannerPipelineState, init=False)
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
    # Scanner pipeline
    # ------------------------------------------------------------------

    def update_quality_universe(self, candidates: list[CandidateContext]) -> None:
        snapshot = ScannerStageSnapshot(
            stage="quality_universe",
            candidates=candidates,
            timestamp=datetime.now(timezone.utc),
        )
        with self._lock:
            self._scanner.quality_universe = snapshot
            self._scanner.candidates.update(candidates)

    def update_active_shortlist(
        self,
        candidates: list[CandidateContext],
        cache: Dict[str, TimeframeData],
    ) -> None:
        timestamp = datetime.now(timezone.utc)
        active_symbols = [candidate.symbol for candidate in candidates if candidate.symbol in cache]
        snapshot = ScannerStageSnapshot(
            stage="active_shortlist",
            candidates=[candidate for candidate in candidates if candidate.symbol in active_symbols],
            timestamp=timestamp,
        )
        scan_snapshot = ScanSnapshot(
            symbols=active_symbols,
            cache=SymbolCache(data={symbol: cache[symbol] for symbol in active_symbols}),
            timestamp=timestamp,
        )
        with self._lock:
            self._scanner.active_shortlist = snapshot
            self._scanner.candidates.update(snapshot.candidates)
            self._scan = scan_snapshot

    def update_sentiment(self, candidates: list[CandidateContext]) -> None:
        snapshot = ScannerStageSnapshot(
            stage="sentiment_enriched",
            candidates=candidates,
            timestamp=datetime.now(timezone.utc),
        )
        with self._lock:
            self._scanner.active_shortlist = snapshot
            self._scanner.candidates.update(candidates)

    def get_candidate(self, symbol: str) -> CandidateContext | None:
        with self._lock:
            return self._scanner.candidates.get(symbol)

    @property
    def quality_universe(self) -> list[CandidateContext]:
        with self._lock:
            if self._scanner.quality_universe is None:
                return []
            return list(self._scanner.quality_universe.candidates)

    @property
    def active_shortlist(self) -> list[CandidateContext]:
        with self._lock:
            if self._scanner.active_shortlist is None:
                return []
            return list(self._scanner.active_shortlist.candidates)

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

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load_from_db(self, session: Session) -> list[str]:
        repo = SystemRepository(session)
        heartbeat = repo.get_last_heartbeat()
        if heartbeat is None:
            return []

        symbols = list(heartbeat.active_symbols or [])
        with self._lock:
            self._scan = ScanSnapshot(
                symbols=symbols,
                cache=SymbolCache(data={}),
                timestamp=datetime.now(timezone.utc),
            )
        return symbols

    def persist_to_db(self, session: Session) -> None:
        repo = SystemRepository(session)
        repo.update_heartbeat(self.symbols)
