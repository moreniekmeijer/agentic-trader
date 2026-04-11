from datetime import datetime, timedelta, timezone
from typing import Dict, List

import pandas as pd
from pydantic import BaseModel

CACHE_MAX_AGE = timedelta(minutes=90)


class TimeframeData(BaseModel):
    """Raw dataframes for one symbol, both timeframes."""

    daily: pd.DataFrame
    h4: pd.DataFrame

    model_config = {"arbitrary_types_allowed": True}


class SymbolCache(BaseModel):
    data: Dict[str, TimeframeData]

    model_config = {"arbitrary_types_allowed": True}

    def get(self, symbol: str) -> TimeframeData | None:
        return self.data.get(symbol)


class ScanSnapshot(BaseModel):
    """Immutable snapshot of the latest scan, passed to trade_job."""

    symbols: List[str]
    cache: SymbolCache
    timestamp: datetime

    model_config = {"arbitrary_types_allowed": True}

    def is_fresh(self, max_age: timedelta = CACHE_MAX_AGE) -> bool:
        return datetime.now(timezone.utc) - self.timestamp < max_age
