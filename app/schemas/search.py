from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from datetime import date

class SortOption(str, Enum):
    RECENCY = "recency"
    RELEVANCE = "relevance"
    RATING_HIGH_TO_LOW = "rating_high_to_low"
    RATING_LOW_TO_HIGH = "rating_low_to_high"
    SALARY_HIGH_TO_LOW = "salary_high_to_low"
    SALARY_LOW_TO_HIGH = "salary_low_to_high"


class DateRange(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class AdvancedSearchParams(BaseModel):
    query: Optional[str] = None
    industries: Optional[List[str]] = Field(default=None, description="List of industries to filter by")
    locations: Optional[List[str]] = Field(default=None, description="List of locations to filter by")
    experience_levels: Optional[List[str]] = Field(default=None, description="List of experience levels to filter by")
    employment_types: Optional[List[str]] = Field(default=None, description="List of employment types to filter by")
    min_rating: Optional[float] = None
    max_rating: Optional[float] = None
    min_salary: Optional[float] = None
    max_salary: Optional[float] = None
    date_range: Optional[DateRange] = None
    sort_by: Optional[SortOption] = SortOption.RECENCY
    skip: int = 0
    limit: int = 20


class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total: int
    filters_applied: Dict[str, Any]
    sort_by: str
    skip: int
    limit: int