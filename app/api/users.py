from typing import Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from starlette import status

from app.db.base import get_db
from app import crud
from app.models.user import User
from app.schemas.user import (
    User as UserSchema,
    UserUpdate,
    UserResponse,
    UserAccountManage,
    PasswordChange,
    EmailChangeRequest,
    EmailChangeConfirm,
)
from app.schemas.settings import AccountSettingsUpdate, AccountSettingsResponse
from app.core.dependencies import get_current_user
from app.services import email

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
        "is_currently_employed": bool(current_user.job_title),
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
            raise HTTPException(status_code=400, detail="Email already registered")

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
            db, user_id=current_user.id, obj_in=AccountSettingsUpdate()
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
        db, user_id=current_user.id, obj_in=settings_in
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
        created_at=current_user.created_at,
    )


@router.post("/me/change-password", response_model=dict)
def change_password(
    *,
    db: Session = Depends(get_db),
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
) -> Any:
    if not crud.user.authenticate(
        db, email=current_user.email, password=password_data.current_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password"
        )

    user_in = UserUpdate(password=password_data.new_password)
    user = crud.user.update(db, db_obj=current_user, obj_in=user_in)

    return {"message": "Password updated successfully"}


@router.post("/me/change-email/request", response_model=dict)
async def request_email_change(
    *,
    db: Session = Depends(get_db),
    email_data: EmailChangeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> Any:
    if not crud.user.authenticate(
        db, email=current_user.email, password=email_data.password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password"
        )

    # Check if the new email is already registered
    existing_user = crud.user.get_by_email(db, email=email_data.new_email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    verification = crud.user.create_email_change_verification(
        db=db, user_id=current_user.id, new_email=email_data.new_email
    )

    background_tasks.add_task(
        email.send_email_change_verification,
        user_email=email_data.new_email,
        user_first_name=current_user.first_name,
        verification_code=verification.verification_code,
    )

    return {"message": "Verification code sent to new email address"}


@router.post("/me/change-email/confirm", response_model=dict)
def confirm_email_change(
    *,
    db: Session = Depends(get_db),
    confirm_data: EmailChangeConfirm,
    current_user: User = Depends(get_current_user),
) -> Any:
    # Verify the code
    verification = crud.user.verify_email_change(
        db=db, user_id=current_user.id, verification_code=confirm_data.verification_code
    )

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    # Update the email
    new_email = verification.new_email
    user = crud.user.complete_email_change(
        db=db, user_id=current_user.id, new_email=new_email
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update email address",
        )

    return {"message": "Email address updated successfully"}
