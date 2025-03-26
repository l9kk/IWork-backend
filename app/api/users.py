from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app import crud
from app.models.user import User
from app.schemas.user import User as UserSchema, UserUpdate, UserResponse, UserAccountManage
from app.schemas.settings import AccountSettingsUpdate, AccountSettingsResponse
from app.core.dependencies import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def read_user_me(
        current_user: User = Depends(get_current_user),
) -> Any:
    user_data = {
        "id": current_user.id,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "full_name": f"{current_user.first_name} {current_user.last_name}".strip(),
        "job_title": current_user.job_title,
        "profile_image": current_user.profile_image,
        "created_at": current_user.created_at,
        "is_currently_employed": bool(current_user.job_title)
    }

    return user_data


@router.put("/me", response_model=UserSchema)
def update_user_me(
        *,
        db: Session = Depends(get_db),
        user_in: UserUpdate,
        current_user: User = Depends(get_current_user),
) -> Any:
    if user_in.email and user_in.email != current_user.email:
        # Check if the new email is not already taken
        user_with_email = crud.user.get_by_email(db, email=user_in.email)
        if user_with_email:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

    user = crud.user.update(db, db_obj=current_user, obj_in=user_in)
    return user


@router.get("/me/settings", response_model=AccountSettingsResponse)
def get_user_settings(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> Any:
    settings = crud.account_settings.get_by_user_id(db, user_id=current_user.id)

    if not settings:
        settings = crud.account_settings.create_or_update(
            db,
            user_id=current_user.id,
            obj_in=AccountSettingsUpdate()
        )

    return settings


@router.put("/me/settings", response_model=AccountSettingsResponse)
def update_user_settings(
        *,
        db: Session = Depends(get_db),
        settings_in: AccountSettingsUpdate,
        current_user: User = Depends(get_current_user),
) -> Any:
    settings = crud.account_settings.create_or_update(
        db,
        user_id=current_user.id,
        obj_in=settings_in
    )

    return settings


@router.get("/me/account", response_model=UserAccountManage)
def get_account_management(
    *,
    current_user: User = Depends(get_current_user),
) -> Any:
    return UserAccountManage(
        id=current_user.id,
        email=current_user.email,
        profile_image=current_user.profile_image,
        full_name=f"{current_user.first_name} {current_user.last_name}".strip(),
        job_title=current_user.job_title,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )