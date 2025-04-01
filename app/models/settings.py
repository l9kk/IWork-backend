from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base


class AccountSettings(Base):
    __tablename__ = "account_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    email_notifications_enabled = Column(Boolean, default=True)
    notify_on_review_approval = Column(Boolean, default=True)
    notify_on_review_rejection = Column(Boolean, default=True)
    notify_on_company_response = Column(Boolean, default=True)

    default_review_anonymity = Column(Boolean, default=False)
    default_salary_anonymity = Column(Boolean, default=True)

    theme_preference = Column(String, default="light")

    user = relationship("User", back_populates="settings")
