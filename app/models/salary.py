from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ExperienceLevel(str, PyEnum):
    INTERN = "intern"
    JUNIOR = "junior"
    MIDDLE = "middle"
    SENIOR = "senior"
    EXECUTIVE = "executive"


class EmploymentType(str, PyEnum):
    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"


class Salary(Base):
    __tablename__ = "salaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    job_title = Column(String, index=True, nullable=False)
    salary_amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    experience_level = Column(Enum(ExperienceLevel), nullable=False)
    employment_type = Column(Enum(EmploymentType), nullable=False, default=EmploymentType.FULL_TIME)
    location = Column(String, nullable=True)
    is_anonymous = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="salaries")
    company = relationship("Company", back_populates="salaries")