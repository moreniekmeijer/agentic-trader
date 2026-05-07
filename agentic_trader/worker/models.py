from datetime import datetime, timedelta, timezone
from typing import Dict, List

import pandas as pd
from pydantic import BaseModel, Field

from agentic_trader.scanner.models import CandidateContext, ScannerStageSnapshot
from agentic_trader.services.fundamentals.models import FundamentalsSnapshot

CACHE_MAX_AGE = timedelta(minutes=90)
FUNDAMENTALS_MAX_AGE = timedelta(hours=24)


class TimeframeData(BaseModel):
    """Raw dataframes for one symbol, both timeframes."""

    daily: pd.DataFrame
    h4: pd.DataFrame

    model_config = {"arbitrary_types_allowed": True}


class SymbolCache(BaseModel):
    """Raw market data per symbol."""

    data: Dict[str, TimeframeData]

    model_config = {"arbitrary_types_allowed": True}

    def get(self, symbol: str) -> TimeframeData | None:
        return self.data.get(symbol)

    def symbols(self) -> List[str]:
        return list(self.data.keys())


class FundamentalsCache(BaseModel):
    """Fundamentals per symbol, refreshed daily."""

    data: Dict[str, FundamentalsSnapshot] = Field(default_factory=dict)

    def get(self, symbol: str) -> FundamentalsSnapshot | None:
        return self.data.get(symbol)

    def is_fresh(self, symbol: str) -> bool:
        snapshot = self.data.get(symbol)
        if snapshot is None:
            return False
        return datetime.now(timezone.utc) - snapshot.fetched_at < FUNDAMENTALS_MAX_AGE

    def update(self, snapshots: Dict[str, FundamentalsSnapshot]) -> None:
        self.data.update(snapshots)


class ScanSnapshot(BaseModel):
    """Immutable snapshot of the last scan."""

    symbols: List[str]
    cache: SymbolCache
    timestamp: datetime

    model_config = {"arbitrary_types_allowed": True}

    def is_fresh(self, max_age: timedelta = CACHE_MAX_AGE) -> bool:
        return datetime.now(timezone.utc) - self.timestamp < max_age


class CandidateCache(BaseModel):
    """Scanner candidates keyed by symbol."""

    data: Dict[str, CandidateContext] = Field(default_factory=dict)

    def get(self, symbol: str) -> CandidateContext | None:
        return self.data.get(symbol)

    def update(self, candidates: list[CandidateContext]) -> None:
        self.data.update({candidate.symbol: candidate for candidate in candidates})

    def list(self) -> list[CandidateContext]:
        return list(self.data.values())


class ScannerPipelineState(BaseModel):
    """Latest outputs from each scanner stage."""

    quality_universe: ScannerStageSnapshot | None = None
    active_shortlist: ScannerStageSnapshot | None = None
    candidates: CandidateCache = Field(default_factory=CandidateCache)
