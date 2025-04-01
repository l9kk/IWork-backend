from typing import Dict, Any
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import timedelta


from app.db.base import get_db
from app.services.oauth import (
    get_google_oauth_url,
    exchange_google_code,
    process_google_user,
)
from app.core.config import settings
from app.core.security import create_access_token
from app import crud

router = APIRouter()


class GoogleAuthCode(BaseModel):
    code: str


@router.get("/google/login")
async def google_login(request: Request):
    """
    Redirect to Google OAuth login page
    """
    return await get_google_oauth_url(request)


@router.post("/google/token")
async def google_token(
    *, db: Session = Depends(get_db), code_data: GoogleAuthCode
) -> Dict[str, Any]:
    """
    Exchange Google auth code for access token and user info
    """
    user_info = await exchange_google_code(code_data.code)

    user, is_new_user = await process_google_user(db, user_info)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(user.id, expires_delta=access_token_expires)

    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_db = crud.refresh_token.create_refresh_token(
        db=db,
        user_id=user.id,
        expires_delta=refresh_token_expires,
        device_name="Google OAuth Login",
        device_ip=None,
        user_agent=None,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token_db.token,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "profile_image": user.profile_image,
            "is_new_user": is_new_user,
        },
    }
