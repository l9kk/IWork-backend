from fastapi.testclient import TestClient

from app.models.company import Company


def test_get_companies(client: TestClient):
    """Test getting list of companies"""
    response = client.get("/companies")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_company(client: TestClient, test_company: Company):
    """Test getting a specific company"""
    response = client.get(f"/companies/{test_company.id}")

    assert response.status_code == 200
    assert response.json()["id"] == test_company.id
    assert response.json()["name"] == test_company.name
    assert "avg_rating" in response.json()
    assert "review_count" in response.json()


def test_get_nonexistent_company(client: TestClient):
    """Test getting a company that doesn't exist"""
    response = client.get("/companies/99999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_company(client: TestClient, token_headers: dict):
    """Test creating a new company"""
    company_data = {
        "name": "New Company via API",
        "industry": "Retail",
        "location": "Chicago, IL",
        "description": "A company created through API testing",
        "is_public": False
    }

    response = client.post("/companies", json=company_data, headers=token_headers)

    assert response.status_code == 200
    assert response.json()["name"] == company_data["name"]
    assert response.json()["industry"] == company_data["industry"]
    assert "id" in response.json()


def test_search_companies(client: TestClient, test_company: Company):
    """Test searching companies"""
    response = client.get("/companies/search", params={"industry": "Technology"})

    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert any(company["id"] == test_company.id for company in response.json())

    response = client.get("/companies/search", params={"query": "Test Company"})

    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert any(company["id"] == test_company.id for company in response.json())