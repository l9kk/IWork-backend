from typing import Optional, List
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

    @validator("salary_amount")
    def salary_positive(cls, v):
        if v <= 0:
            raise ValueError("Salary amount must be positive")
        return v

    @classmethod
    def _validate_enum(cls, v, enum_class, default_value=None):
        if isinstance(v, enum_class):
            return v
        if isinstance(v, str):
            try:
                return enum_class(v)
            except ValueError:
                try:
                    return getattr(enum_class, v)
                except (AttributeError, TypeError):
                    if default_value:
                        return default_value
                    raise ValueError(f"Invalid {enum_class.__name__} value: {v}")
        raise ValueError(f"Invalid {enum_class.__name__} type: {type(v)}")

    @validator("experience_level")
    def validate_experience_level(cls, v):
        return cls._validate_enum(v, ExperienceLevel, ExperienceLevel.INTERN)

    @validator("employment_type")
    def validate_employment_type(cls, v):
        return cls._validate_enum(v, EmploymentType, EmploymentType.FULL_TIME)

    @property
    def experience_level_value(self) -> str:
        return getattr(self.experience_level, "value", "intern")

    @property
    def employment_type_value(self) -> str:
        return getattr(self.employment_type, "value", "full-time")


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

    @validator("salary_amount")
    def salary_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Salary amount must be positive")
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

    model_config = {"from_attributes": True}


class SalaryStatistics(BaseModel):
    job_title: str
    avg_salary: float
    min_salary: float
    max_salary: float
    sample_size: int
    currency: str


class UserSalariesResponse(BaseModel):
    total_count: int
    salaries: List[SalaryResponse]

    model_config = {"from_attributes": True}
