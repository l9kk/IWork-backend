from typing import Optional, List, Any, Dict
from pydantic import BaseModel, validator
from datetime import datetime

from app.models.review import ReviewStatus, EmployeeStatus


class ReviewBase(BaseModel):
    company_id: int
    rating: float
    employee_status: EmployeeStatus
    employment_start_date: Optional[datetime] = None
    employment_end_date: Optional[datetime] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    recommendations: Optional[str] = None
    is_anonymous: bool = False

    @validator('rating')
    def rating_range(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Rating must be between 1 and 5')
        return v

    @validator('employment_end_date')
    def end_date_after_start_date(cls, v, values):
        if v is not None and 'employment_start_date' in values and values['employment_start_date'] is not None:
            if v < values['employment_start_date']:
                raise ValueError('End date must be after start date')
        return v


class ReviewCreate(ReviewBase):
    pass


class ReviewUpdate(BaseModel):
    rating: Optional[float] = None
    employee_status: Optional[EmployeeStatus] = None
    employment_start_date: Optional[datetime] = None
    employment_end_date: Optional[datetime] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    recommendations: Optional[str] = None
    is_anonymous: Optional[bool] = None

    @validator('rating')
    def rating_range(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError('Rating must be between 1 and 5')
        return v

    @validator('employment_end_date')
    def end_date_after_start_date(cls, v, values):
        if v is not None and 'employment_start_date' in values and values['employment_start_date'] is not None:
            if v < values['employment_start_date']:
                raise ValueError('End date must be after start date')
        return v


class ReviewResponse(BaseModel):
    id: int
    company_id: int
    company_name: str
    rating: float
    employee_status: EmployeeStatus
    employment_start_date: Optional[datetime] = None
    employment_end_date: Optional[datetime] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    recommendations: Optional[str] = None
    status: ReviewStatus
    created_at: datetime
    user_name: Optional[str] = None

    class Config:
        orm_mode = True


class AIScannerFlagResponse(BaseModel):
    flag_type: str
    flag_description: str
    flagged_text: Optional[str] = None


class AdminReviewResponse(ReviewResponse):
    user_id: int
    moderation_notes: Optional[str] = None
    ai_scanner_flags: List[Dict[str, Any]] = []