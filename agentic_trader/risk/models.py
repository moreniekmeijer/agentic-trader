from pydantic import BaseModel


class RiskVerdict(BaseModel):
    allowed: bool
    reason: str | None = None
