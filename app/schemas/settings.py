from typing import Optional
from pydantic import BaseModel


class AccountSettingsBase(BaseModel):
    email_notifications_enabled: bool = True
    notify_on_review_approval: bool = True
    notify_on_review_rejection: bool = True
    notify_on_company_response: bool = True
    default_review_anonymity: bool = False
    default_salary_anonymity: bool = True
    theme_preference: str = "light"


class AccountSettingsUpdate(AccountSettingsBase):
    email_notifications_enabled: Optional[bool] = None
    notify_on_review_approval: Optional[bool] = None
    notify_on_review_rejection: Optional[bool] = None
    notify_on_company_response: Optional[bool] = None
    default_review_anonymity: Optional[bool] = None
    default_salary_anonymity: Optional[bool] = None
    theme_preference: Optional[str] = None


class AccountSettingsResponse(AccountSettingsBase):
    id: int
    user_id: int

    model_config = {
        "from_attributes": True
    }