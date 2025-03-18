from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.core.config import settings
from app.db.base import get_db
from app.models.user import User
from app import crud
from app.schemas.user import User as UserSchema, UserCreate
from app.schemas.token import Token, TokenRefresh
from app.schemas.settings import AccountSettingsUpdate

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


@router.post("/auth/logout-all", status_code=status.HTTP_200_OK)
def logout_all_devices(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
) -> Any:
    crud.refresh_token.revoke_all_user_tokens(db, user_id=current_user.id)

    return {"message": "Successfully logged out from all devices"}


@router.post("/auth/register", response_model=UserSchema)
def register_new_user(
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

    return user