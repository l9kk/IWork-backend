import pytest
from fastapi.testclient import TestClient

from app.models.review import Review, ReviewStatus
from app.models.company import Company
from app.models.user import User


def test_get_company_reviews(client: TestClient, test_review: Review, test_company: Company):
    """Test getting reviews for a company"""
    response = client.get(f"/reviews/company/{test_company.id}")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1
    assert any(review["id"] == test_review.id for review in response.json())


def test_create_review(client: TestClient, token_headers: dict, test_company: Company):
    """Test creating a new review"""
    review_data = {
        "company_id": test_company.id,
        "rating": 4.0,
        "employee_status": "CURRENT",
        "pros": "Great culture and benefits",
        "cons": "Work-life balance could be better",
        "recommendations": "Implement more flexible hours",
        "is_anonymous": False
    }

    response = client.post("/reviews", json=review_data, headers=token_headers)

    assert response.status_code == 200
    assert response.json()["company_id"] == test_company.id
    assert response.json()["rating"] == 4.0
    assert response.json()["status"] == ReviewStatus.PENDING.value


def test_get_review(client: TestClient, test_review: Review):
    """Test getting a specific review"""
    response = client.get(f"/reviews/{test_review.id}")

    assert response.status_code == 200
    assert response.json()["id"] == test_review.id
    assert response.json()["rating"] == test_review.rating
    assert response.json()["pros"] == test_review.pros


def test_get_user_reviews(client: TestClient, token_headers: dict, test_review: Review, test_user: User):
    """Test getting reviews by current user"""
    response = client.get("/reviews/me", headers=token_headers)

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1
    assert any(review["id"] == test_review.id for review in response.json())


def test_update_review(client: TestClient, token_headers: dict, test_review: Review):
    """Test updating a review"""
    update_data = {
        "rating": 3.5,
        "pros": "Updated pros content",
        "recommendations": "Updated recommendations"
    }

    response = client.put(
        f"/reviews/{test_review.id}",
        json=update_data,
        headers=token_headers
    )

    assert response.status_code == 200
    assert response.json()["rating"] == 3.5
    assert response.json()["pros"] == "Updated pros content"
    assert response.json()["recommendations"] == "Updated recommendations"
    assert response.json()["cons"] == test_review.cons