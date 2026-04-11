from pydantic import BaseModel


class ScanResult(BaseModel):
    symbol: str
    score: float
    rsi: float
    volume: float
    price: float
