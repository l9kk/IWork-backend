from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def test_login(client: TestClient, test_user: User):
    """Test user login endpoint"""
    login_data = {
        "username": test_user.email,
        "password": "password123"
    }

    response = client.post("/auth/login", data=login_data)

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient, test_user: User):
    """Test login with wrong password"""
    login_data = {
        "username": test_user.email,
        "password": "wrongpassword"
    }

    response = client.post("/auth/login", data=login_data)

    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_register(client: TestClient, db: Session):
    """Test user registration endpoint"""
    user_data = {
        "email": "newregistration@example.com",
        "password": "securepassword123",
        "first_name": "New",
        "last_name": "Registration"
    }

    response = client.post("/auth/register", json=user_data)

    assert response.status_code == 200
    assert response.json()["email"] == user_data["email"]
    assert response.json()["first_name"] == user_data["first_name"]
    assert response.json()["last_name"] == user_data["last_name"]
    assert "id" in response.json()


def test_register_existing_email(client: TestClient, test_user: User):
    """Test registration with existing email"""
    user_data = {
        "email": test_user.email,
        "password": "securepassword123",
        "first_name": "Duplicate",
        "last_name": "User"
    }

    response = client.post("/auth/register", json=user_data)

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_refresh_token(client: TestClient, test_user: User):
    """Test refresh token endpoint"""
    login_data = {
        "username": test_user.email,
        "password": "password123"
    }

    login_response = client.post("/auth/login", data=login_data)
    refresh_token = login_response.json()["refresh_token"]

    refresh_data = {
        "refresh_token": refresh_token
    }

    response = client.post("/auth/refresh", json=refresh_data)

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_logout(client: TestClient, test_user: User):
    """Test logout endpoint"""
    login_data = {
        "username": test_user.email,
        "password": "password123"
    }

    login_response = client.post("/auth/login", data=login_data)
    refresh_token = login_response.json()["refresh_token"]

    logout_data = {
        "refresh_token": refresh_token
    }

    response = client.post("/auth/logout", json=logout_data)

    assert response.status_code == 200
    assert "message" in response.json()
    assert "successfully" in response.json()["message"].lower()