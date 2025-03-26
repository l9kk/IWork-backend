from sqlalchemy.orm import Session

from app import crud
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import verify_password

def test_create_user(db: Session):
    """Test creating a new user"""
    user_in = UserCreate(
        email="newuser@example.com",
        password="testpassword",
        first_name="New",
        last_name="User"
    )

    user = crud.user.create(db, obj_in=user_in)

    assert user.email == "newuser@example.com"
    assert user.first_name == "New"
    assert user.last_name == "User"
    assert verify_password("testpassword", user.hashed_password)
    assert user.is_active is True
    assert user.is_admin is False


def test_get_user(db: Session, test_user: User):
    """Test retrieving a user by ID"""
    user = crud.user.get(db, id=test_user.id)

    assert user is not None
    assert user.id == test_user.id
    assert user.email == test_user.email


def test_get_user_by_email(db: Session, test_user: User):
    """Test retrieving a user by email"""
    user = crud.user.get_by_email(db, email=test_user.email)

    assert user is not None
    assert user.id == test_user.id
    assert user.email == test_user.email


def test_update_user(db: Session, test_user: User):
    """Test updating a user"""
    user_update = UserUpdate(
        first_name="Updated",
        last_name="Name"
    )

    updated_user = crud.user.update(db, db_obj=test_user, obj_in=user_update)

    assert updated_user.first_name == "Updated"
    assert updated_user.last_name == "Name"
    assert updated_user.email == test_user.email


def test_update_user_with_password(db: Session, test_user: User):
    """Test updating a user's password"""
    new_password = "newpassword123"
    user_update = UserUpdate(password=new_password)

    updated_user = crud.user.update(db, db_obj=test_user, obj_in=user_update)

    assert verify_password(new_password, updated_user.hashed_password)


def test_authenticate_user(db: Session, test_user: User):
    """Test user authentication"""
    authenticated_user = crud.user.authenticate(
        db, email=test_user.email, password="password123"
    )

    assert authenticated_user is not None
    assert authenticated_user.id == test_user.id

    non_authenticated_user = crud.user.authenticate(
        db, email=test_user.email, password="wrongpassword"
    )

    assert non_authenticated_user is None