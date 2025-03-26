from datetime import datetime, timedelta
from jose import jwt

from app.core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    ALGORITHM
)
from app.core.config import settings


def test_password_hashing():
    """Test password hashing and verification"""
    password = "testpassword123"
    hashed = get_password_hash(password)

    assert hashed != password

    assert verify_password(password, hashed) is True

    assert verify_password("wrongpassword", hashed) is False


def test_create_access_token():
    """Test creating JWT access tokens"""
    user_id = 123
    token = create_access_token(subject=user_id)

    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == str(user_id)
    assert "exp" in payload
    assert "jti" in payload
    assert payload["type"] == "access"

    expires_delta = timedelta(minutes=30)
    token = create_access_token(subject=user_id, expires_delta=expires_delta)

    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == str(user_id)
    assert "exp" in payload

    exp_time = datetime.fromtimestamp(payload["exp"])
    now_plus_30 = datetime.utcnow() + expires_delta
    assert abs((exp_time - now_plus_30).total_seconds()) < 10