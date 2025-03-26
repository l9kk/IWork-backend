from fastapi.testclient import TestClient

from app.models.user import User


def test_get_current_user(client: TestClient, token_headers: dict, test_user: User):
    """Test getting current user info"""
    response = client.get("/users/me", headers=token_headers)

    assert response.status_code == 200
    assert response.json()["email"] == test_user.email
    assert response.json()["id"] == test_user.id
    assert "hashed_password" not in response.json()


def test_get_current_user_unauthorized(client: TestClient):
    """Test getting current user without token"""
    response = client.get("/users/me")

    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


def test_update_user(client: TestClient, token_headers: dict):
    """Test updating user info"""
    update_data = {
        "first_name": "Updated",
        "last_name": "Profile",
        "job_title": "Software Developer"
    }

    response = client.put("/users/me", json=update_data, headers=token_headers)

    assert response.status_code == 200
    assert response.json()["first_name"] == update_data["first_name"]
    assert response.json()["last_name"] == update_data["last_name"]
    assert response.json()["job_title"] == update_data["job_title"]


def test_update_user_password(client: TestClient, token_headers: dict):
    """Test updating user password"""
    update_data = {
        "password": "newpassword456"
    }

    response = client.put("/users/me", json=update_data, headers=token_headers)

    assert response.status_code == 200

    login_data = {
        "username": response.json()["email"],
        "password": "newpassword456"
    }

    login_response = client.post("/auth/login", data=login_data)
    assert login_response.status_code == 200