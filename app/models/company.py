from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    industry = Column(String, index=True, nullable=True)
    location = Column(String, index=True, nullable=True)
    logo_url = Column(String, nullable=True)
    website = Column(String, nullable=True)
    founded_year = Column(Integer, nullable=True)
    is_public = Column(Boolean, default=False)
    stock_symbol = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    reviews = relationship("Review", back_populates="company", cascade="all, delete-orphan")
    salaries = relationship("Salary", back_populates="company", cascade="all, delete-orphan")

    sec_cik = Column(String, nullable=True, index=True)