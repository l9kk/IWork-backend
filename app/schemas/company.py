from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.schemas.integrations import StockDataResponse, TaxDataResponse


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


class CompanyDetail(CompanyResponse):
    description: Optional[str]
    website: Optional[str]
    founded_year: Optional[int]
    is_public: bool
    stock_symbol: Optional[str]
    sec_cik: Optional[str]
    avg_rating: float
    review_count: int
    stock_data: Optional[StockDataResponse] = None
    tax_data: Optional[TaxDataResponse] = None

    model_config = {
        "from_attributes": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        },
        "arbitrary_types_allowed": True
    }