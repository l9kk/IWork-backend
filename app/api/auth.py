from datetime import timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import crud
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import ALGORITHM
from app.core.security import create_access_token
from app.db.base import get_db
from app.models import User
from app.schemas.password_reset import EmailVerification, PasswordResetRequest, PasswordReset
from app.schemas.settings import AccountSettingsUpdate
from app.schemas.token import Token, TokenRefresh
from app.schemas.user import User as UserSchema, UserCreate
from app.services.email import (
    send_verification_email,
    send_password_reset_email,
)

router = APIRouter()


@router.post("/auth/login", response_model=Token)
def login_access_token(
        request: Request,
        db: Session = Depends(get_db),
        form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    user = crud.user.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not crud.user.is_active(user):
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        user.id, expires_delta=access_token_expires
    )

    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    user_agent = request.headers.get("user-agent", "")
    client_ip = request.client.host if request.client else None

    refresh_token_db = crud.refresh_token.create_refresh_token(
        db=db,
        user_id=user.id,
        expires_delta=refresh_token_expires,
        device_ip=client_ip,
        user_agent=user_agent
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_db.token,
    }


@router.post("/auth/refresh", response_model=Token)
def refresh_token(
        request: Request,
        db: Session = Depends(get_db),
        token_data: TokenRefresh = None,
) -> Any:
    if not token_data or not token_data.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required"
        )

    refresh_token_db = crud.refresh_token.get_by_token(db, token=token_data.refresh_token)

    if not refresh_token_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not crud.refresh_token.is_valid(refresh_token_db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired or revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = crud.user.get(db, id=refresh_token_db.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    crud.refresh_token.revoke_token(db, token=token_data.refresh_token)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        user.id, expires_delta=access_token_expires
    )

    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # Get client information
    user_agent = request.headers.get("user-agent", "")
    client_ip = request.client.host if request.client else None

    new_refresh_token = crud.refresh_token.create_refresh_token(
        db=db,
        user_id=user.id,
        expires_delta=refresh_token_expires,
        device_ip=client_ip,
        user_agent=user_agent
    )

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token.token,
    }


@router.post("/auth/logout", status_code=status.HTTP_200_OK)
def logout(
        db: Session = Depends(get_db),
        token_data: TokenRefresh = None,
) -> Any:
    if not token_data or not token_data.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required"
        )

    crud.refresh_token.revoke_token(db, token=token_data.refresh_token)

    return {"message": "Successfully logged out"}

@router.post("/auth/register", response_model=UserSchema)
async def register_new_user(
        *,
        db: Session = Depends(get_db),
        user_in: UserCreate
) -> Any:
    user = crud.user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists",
        )

    user = crud.user.create(db, obj_in=user_in)

    crud.account_settings.create_or_update(
        db,
        user_id=user.id,
        obj_in=AccountSettingsUpdate()
    )

    # Send verification email
    await send_verification_email(
        user_email=user.email,
        user_first_name=user.first_name or "User",
        user_id=user.id
    )

    return user


@router.post("/auth/verify-email", response_model=Dict[str, str])
def verify_email(
        *,
        db: Session = Depends(get_db),
        verification_data: EmailVerification
):
    try:
        payload = jwt.decode(
            verification_data.token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )

        jti = payload.get("jti", "")
        if not jti or not jti.startswith("verification_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token"
            )

        user = crud.user.get(db, id=int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user.is_verified:
            return {"message": "Email already verified"}

        crud.user.verify_email(db, user_id=user.id)
        return {"message": "Email verified successfully"}

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )


@router.post("/auth/request-verification-email", response_model=Dict[str, str])
async def request_verification_email(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Send a password reset email.
    """
    if current_user.is_verified:
        return {"message": "Email already verified"}

    await send_verification_email(
        user_email=current_user.email,
        user_first_name=current_user.first_name or "User",
        user_id=current_user.id
    )

    return {"message": "Verification email sent"}


@router.post("/auth/forgot-password", response_model=Dict[str, str])
async def forgot_password(
        *,
        db: Session = Depends(get_db),
        reset_request: PasswordResetRequest
):
    user = crud.user.get_by_email(db, email=reset_request.email)
    if not user:
        return {"message": "If your email is registered, you will receive a password reset link"}

    await send_password_reset_email(
        user_email=user.email,
        user_first_name=user.first_name or "User",
        user_id=user.id
    )

    return {"message": "If your email is registered, you will receive a password reset link"}


@router.post("/auth/reset-password", response_model=Dict[str, str])
def reset_password(
        *,
        db: Session = Depends(get_db),
        reset_data: PasswordReset
):
    """
    Reset a user's password using the reset token.
    """
    try:
        payload = jwt.decode(
            reset_data.token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )

        jti = payload.get("jti", "")
        if not jti or not jti.startswith("password_reset_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset token"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset token"
            )

        user = crud.user.get(db, id=int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        crud.user.reset_password(db, user_id=user.id, new_password=reset_data.new_password)

        crud.refresh_token.revoke_all_user_tokens(db, user_id=user.id)

        return {"message": "Password reset successfully"}

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )