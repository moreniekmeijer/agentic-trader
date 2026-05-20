from sqlalchemy.orm import Session
from agentic_trader.database.models import PositionMeta, PositionReviewRecord


class PositionMetaRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_symbol(self, symbol: str) -> PositionMeta | None:
        return self.session.query(PositionMeta).filter_by(symbol=symbol.upper()).first()

    def create_or_update(
        self,
        symbol: str,
        decision_id: int | None = None,
        thesis: str | None = None,
        invalidation: str | None = None,
        expected_horizon_days: int | None = None,
    ) -> PositionMeta:
        meta = self.get_by_symbol(symbol)
        if not meta:
            meta = PositionMeta(symbol=symbol.upper())
            self.session.add(meta)
        
        if decision_id is not None:
            meta.decision_id = decision_id
        if thesis is not None:
            meta.thesis = thesis
        if invalidation is not None:
            meta.invalidation = invalidation
        if expected_horizon_days is not None:
            meta.expected_horizon_days = expected_horizon_days
            
        return meta

    def add_review_record(
        self,
        symbol: str,
        action: str,
        accepted: bool,
        rejection_reason: str | None,
        reasoning: list[str],
        data: dict | None = None,
    ) -> None:
        record = PositionReviewRecord(
            symbol=symbol.upper(),
            action=action,
            accepted=accepted,
            rejection_reason=rejection_reason,
            reasoning=reasoning,
            data=data or {},
        )
        self.session.add(record)

