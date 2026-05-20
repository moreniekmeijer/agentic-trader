from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from agentic_trader.database.models import MarketState, FundamentalsData


class MarketStateRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_active_shortlist(self) -> list[str]:
        state = self.session.query(MarketState).filter_by(key="active_shortlist").first()
        return state.symbols if state else []

    def set_active_shortlist(self, symbols: list[str]) -> None:
        state = self.session.query(MarketState).filter_by(key="active_shortlist").first()
        if not state:
            state = MarketState(key="active_shortlist", symbols=symbols)
            self.session.add(state)
        else:
            state.symbols = symbols

    def get_fundamentals(self, symbol: str) -> dict | None:
        fd = self.session.query(FundamentalsData).filter_by(symbol=symbol).first()
        return fd.data if fd else None

    def save_fundamentals(self, symbol: str, data: dict) -> None:
        fd = self.session.query(FundamentalsData).filter_by(symbol=symbol).first()
        if not fd:
            fd = FundamentalsData(symbol=symbol, data=data)
            self.session.add(fd)
        else:
            fd.data = data

    def fundamentals_are_stale(self, symbol: str, stale_days: int = 7) -> bool:
        record = self.session.query(FundamentalsData).filter_by(symbol=symbol).first()
        if record is None or record.updated_at is None:
            return True

        updated_at = record.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        return datetime.now(timezone.utc) - updated_at >= timedelta(days=stale_days)
