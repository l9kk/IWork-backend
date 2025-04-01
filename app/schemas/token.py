from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TokenBase(BaseModel):
    access_token: str


class Token(TokenBase):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: int
    exp: datetime
    jti: Optional[str] = None


class RefreshTokenCreate(BaseModel):
    user_id: int
    token: str
    expires_at: datetime
    device_name: Optional[str] = None
    device_ip: Optional[str] = None
    user_agent: Optional[str] = None


class TokenRefresh(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
