from typing import Optional
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime


class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    profile_image: Optional[str] = None
    is_admin: bool = False
    is_verified: Optional[bool] = None

class UserCreate(UserBase):
    email: EmailStr
    password: str
    first_name: str
    last_name: str

    @validator('password')
    def password_min_length(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class UserUpdate(UserBase):
    password: Optional[str] = None

    @validator('password')
    def password_min_length(cls, v):
        if v is not None and len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class UserInDBBase(UserBase):
    id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class User(UserInDBBase):
    pass


class UserInDB(UserInDBBase):
    hashed_password: str


class UserResponse(UserInDBBase):
    full_name: str
    is_currently_employed: bool = False

    model_config = {
        "from_attributes": True
    }

    @validator('full_name', pre=True, always=True)
    def set_full_name(cls, v, values):
        if v:
            return v
        first_name = values.get('first_name', '')
        last_name = values.get('last_name', '')
        if first_name or last_name:
            return f"{first_name} {last_name}".strip()
        return ""


class UserAccountManage(BaseModel):
    id: int
    email: str
    profile_image: Optional[str] = None
    full_name: str
    job_title: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

    @validator('full_name', pre=True, always=True)
    def set_full_name(cls, v, values):
        if isinstance(v, str) and v:
            return v
        return v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @validator('new_password')
    def password_min_length(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

class EmailChangeRequest(BaseModel):
    new_email: EmailStr
    password: str

class EmailChangeConfirm(BaseModel):
    verification_code: str