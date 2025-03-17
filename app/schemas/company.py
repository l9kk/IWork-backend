from typing import Optional
from pydantic import BaseModel


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

    class Config:
        orm_mode = True


class CompanyDetail(CompanyResponse):
    description: Optional[str]
    website: Optional[str]
    founded_year: Optional[int]
    is_public: bool
    stock_symbol: Optional[str]
    avg_rating: float
    review_count: int

    class Config:
        orm_mode = True