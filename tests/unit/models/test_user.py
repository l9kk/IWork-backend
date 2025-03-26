from sqlalchemy.orm import Session

from app.models.user import User


def test_user_model(db: Session, test_user: User):
    """Test user model retrieval"""
    db_user = db.query(User).filter(User.id == test_user.id).first()

    assert db_user is not None
    assert db_user.email == "testuser@example.com"
    assert db_user.first_name == "Test"
    assert db_user.last_name == "User"
    assert db_user.is_active is True
    assert db_user.is_admin is False
    assert db_user.is_verified is True