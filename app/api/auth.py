from datetime import timedelta
from typing import Any, Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.core.config import settings
from app.db.base import get_db
from app import crud
from app.schemas.user import User as UserSchema, UserCreate, Token, LoginRequest
from app.schemas.settings import AccountSettingsUpdate

router = APIRouter()


async def form_data_from_json(login_data: LoginRequest) -> Any:
    class FormData:
        def __init__(self, username: str, password: str):
            self.username = username
            self.password = password
            self.scope = ""
            self.client_id = None
            self.client_secret = None
            self.grant_type = "password"

    return FormData(username=login_data.username, password=login_data.password)

@router.post("/auth/login", response_model=Token)
def login_access_token(
        db: Session = Depends(get_db),
        form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:

    user = crud.user.authenticate(
        db, form_data.username, form_data.password
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

    return {
        "access_token": create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.post("/auth/json-login", response_model=Token)
async def login_json(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends(form_data_from_json)],
        db: Session = Depends(get_db)
) -> Any:
    return login_access_token(db=db, form_data=form_data)

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