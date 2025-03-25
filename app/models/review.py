from enum import Enum as PyEnum
from sqlalchemy import Boolean, Column, Integer, String, Float, Text, DateTime, ForeignKey, Enum, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import TSVECTOR


from app.db.base import Base


class ReviewStatus(str, PyEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class EmployeeStatus(str, PyEnum):
    CURRENT = "current"
    FORMER = "former"


class AIScannerFlag(Base):
    __tablename__ = "ai_scanner_flags"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    flag_type = Column(String, nullable=False)
    flag_description = Column(String, nullable=False)
    flagged_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    review = relationship("Review", back_populates="ai_scanner_flags")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Float, nullable=False)
    employee_status = Column(Enum(EmployeeStatus), nullable=False)
    employment_start_date = Column(DateTime, nullable=True)
    employment_end_date = Column(DateTime, nullable=True)
    pros = Column(Text, nullable=True)
    cons = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)
    is_anonymous = Column(Boolean, default=False)
    status = Column(Enum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False)
    moderation_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    search_vector = Column(TSVECTOR, nullable=True)

    __table_args__ = (
        Index('idx_review_search_vector', search_vector, postgresql_using='gin'),
    )

    # Relationships
    user = relationship("User", back_populates="reviews")
    company = relationship("Company", back_populates="reviews")
    ai_scanner_flags = relationship("AIScannerFlag", back_populates="review", cascade="all, delete-orphan")

    file_attachments = relationship("FileAttachment", back_populates="review", cascade="all, delete-orphan")