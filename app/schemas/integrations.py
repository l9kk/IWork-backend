from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class StockDataResponse(BaseModel):
    symbol: str
    company_name: str
    current_price: Optional[float] = None
    previous_close: Optional[float] = None
    open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    price_change: Optional[float] = None
    price_change_percent: Optional[float] = None
    formatted_price: Optional[str] = None
    formatted_market_cap: Optional[str] = None
    timestamp: Optional[str] = None
    currency: Optional[str] = None


class HistoricalStockDataPoint(BaseModel):
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
    data: List[HistoricalStockDataPoint]
    timestamp: Optional[str] = None


class TaxDataResponse(BaseModel):
    company_name: str
    cik: Optional[str] = None
    symbol: Optional[str] = None
    yearly_taxes: Optional[List[Dict[str, Any]]] = None
    data_source: Optional[str] = None
    retrieved_at: Optional[str] = None
    note: Optional[str] = None
