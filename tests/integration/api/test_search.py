from fastapi.testclient import TestClient

from app.models.review import Review
from app.models.company import Company


def test_fulltext_search(client: TestClient, test_review: Review, test_company: Company):
    """Test full-text search across entities"""
    search_term = "team"

    response = client.get(f"/search/fulltext?query={search_term}")

    assert response.status_code == 200
    assert "reviews" in response.json()
    assert "companies" in response.json()
    assert "total_counts" in response.json()

    if response.json()["reviews"]:
        assert len(response.json()["reviews"]) >= 1


def test_search_reviews(client: TestClient, test_review: Review):
    """Test search reviews endpoint"""
    search_term = "benefits"

    response = client.get(f"/search/reviews?query={search_term}")

    assert response.status_code == 200
    assert "results" in response.json()
    assert "total" in response.json()

    if response.json()["results"]:
        assert "highlight" in response.json()["results"][0]


def test_search_companies(client: TestClient, test_company: Company):
    """Test search companies endpoint"""
    search_term = "Technology"

    response = client.get(f"/search/companies?query={search_term}")

    assert response.status_code == 200
    assert "results" in response.json()
    assert "total" in response.json()

    assert len(response.json()["results"]) >= 1
    assert any(company["id"] == test_company.id for company in response.json()["results"])