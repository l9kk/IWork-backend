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

    class Config:
        orm_mode = True


class User(UserInDBBase):
    pass


class UserInDB(UserInDBBase):
    hashed_password: str
