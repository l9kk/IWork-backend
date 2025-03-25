from typing import List, Optional
from pydantic import BaseModel


class StockDataResponse(BaseModel):
    symbol: str
    company_name: str
    current_price: Optional[float] = None
    formatted_price: str
    price_change: Optional[float] = None
    price_change_percent: Optional[float] = None
    previous_close: Optional[float] = None
    open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    formatted_market_cap: str
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    timestamp: str
    currency: str


class HistoricalDataPoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class HistoricalStockDataResponse(BaseModel):
    symbol: str
    period: str
    interval: str
    data: List[HistoricalDataPoint]
    timestamp: str


class TaxEntry(BaseModel):
    year: str
    amount: float
    formatted_amount: str
    source: str


class TaxDataResponse(BaseModel):
    company_name: str
    yearly_taxes: List[TaxEntry]
    data_source: str
    retrieved_at: str
    cik: Optional[str] = None
    symbol: Optional[str] = None
    note: Optional[str] = None