from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.schemas.integrations import StockDataResponse, TaxDataResponse, HistoricalStockDataResponse
from app.schemas.review import ReviewResponse


class CompanyBase(BaseModel):
    name: str
    description: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    founded_year: Optional[int] = None
    is_public: bool = False
    stock_symbol: Optional[str] = None
    sec_cik: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(CompanyBase):
    name: Optional[str] = None


class CompanyResponse(BaseModel):
    id: int
    name: str
    industry: Optional[str]
    location: Optional[str]
    logo_url: Optional[str]

    model_config = {
        "from_attributes": True
    }


class RecommendedCompanyResponse(BaseModel):
    id: int
    name: str
    logo_url: Optional[str]
    avg_rating: float
    review_count: int

    model_config = {
        "from_attributes": True
    }


class CompanyDetail(CompanyResponse):
    description: Optional[str]
    website: Optional[str]
    founded_year: Optional[int]
    is_public: bool
    stock_symbol: Optional[str]
    sec_cik: Optional[str]
    avg_rating: float
    review_count: int
    competitors: Optional[List[CompanyResponse]] = None
    random_review: Optional[ReviewResponse] = None
    recommended_companies: Optional[List[RecommendedCompanyResponse]] = None
    annual_revenue: Optional[float] = None
    annual_revenue_formatted: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        },
        "arbitrary_types_allowed": True
    }


class CompanyFinancials(BaseModel):
    id: int
    name: str
    is_public: bool
    stock_symbol: Optional[str] = None
    sec_cik: Optional[str] = None
    industry: Optional[str] = None
    stock_data: Optional[StockDataResponse] = None
    historical_stock_data: Optional[HistoricalStockDataResponse] = None
    tax_data: Optional[TaxDataResponse] = None
    annual_revenue: Optional[float] = None
    annual_revenue_formatted: Optional[str] = None
    revenue_trend: Optional[List[Dict[str, Any]]] = None
    key_metrics: Optional[Dict[str, Any]] = None
    industry_comparison: Optional[List[Dict[str, Any]]] = None

    model_config = {
        "from_attributes": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        },
        "arbitrary_types_allowed": True
    }