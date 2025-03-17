from typing import Optional
from pydantic import BaseModel, validator
from datetime import datetime

from app.models.salary import ExperienceLevel, EmploymentType


class SalaryBase(BaseModel):
    company_id: int
    job_title: str
    salary_amount: float
    currency: str = "USD"
    experience_level: ExperienceLevel
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    location: Optional[str] = None
    is_anonymous: bool = True

    @validator('salary_amount')
    def salary_positive(cls, v):
        if v <= 0:
            raise ValueError('Salary amount must be positive')
        return v


class SalaryCreate(SalaryBase):
    pass


class SalaryUpdate(BaseModel):
    job_title: Optional[str] = None
    salary_amount: Optional[float] = None
    currency: Optional[str] = None
    experience_level: Optional[ExperienceLevel] = None
    employment_type: Optional[EmploymentType] = None
    location: Optional[str] = None
    is_anonymous: Optional[bool] = None

    @validator('salary_amount')
    def salary_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Salary amount must be positive')
        return v


class SalaryResponse(BaseModel):
    id: int
    company_id: int
    company_name: str
    job_title: str
    salary_amount: float
    currency: str
    experience_level: ExperienceLevel
    employment_type: EmploymentType
    location: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class SalaryStatistics(BaseModel):
    job_title: str
    avg_salary: float
    min_salary: float
    max_salary: float
    sample_size: int
    currency: str