import unittest.mock
from typing import Dict, Generator, Callable, Any, AsyncGenerator

import re
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy_utils import database_exists, create_database, drop_database

from app.core.config import settings
from app.db.base import Base, get_db
from app.main import app
from app.models.user import User
from app.models.company import Company
from app.models.review import Review, ReviewStatus
from app.models.salary import Salary, ExperienceLevel, EmploymentType
from app.core.security import get_password_hash
from tests.mocks import MockEmailService, AsyncMockSendEmail

TEST_DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI.replace(
    "iwork", "iwork_test"
)

username = "postgres_test"
password = "postgres_test"

user_pass_match = re.search(r'//([^:]+):([^@]+)@', TEST_DATABASE_URL)
if user_pass_match:
    username, password = user_pass_match.groups()

TEST_DATABASE_URL = re.sub(
    r'//([^:]+):([^@]+)@',
    f'//{username}:{password}@',
    TEST_DATABASE_URL
)

TEST_DATABASE_URL = re.sub(
    r'\?sslmode=require',
    '?sslmode=disable',
    TEST_DATABASE_URL
)

if 'sslmode=' not in TEST_DATABASE_URL:
    if '?' in TEST_DATABASE_URL:
        TEST_DATABASE_URL += "&sslmode=disable"
    else:
        TEST_DATABASE_URL += "?sslmode=disable"

print(f"Using test database URL: {TEST_DATABASE_URL}")

engine = create_engine(TEST_DATABASE_URL)


@pytest.fixture(scope="session")
def setup_test_db() -> Generator:
    if not database_exists(TEST_DATABASE_URL):
        create_database(TEST_DATABASE_URL)

    Base.metadata.create_all(bind=engine)

    yield

    drop_database(TEST_DATABASE_URL)


@pytest.fixture(scope="function")
def db(setup_test_db) -> Generator:
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


@pytest.fixture(scope="function")
def override_get_db(db: Session) -> Callable[[], Generator[Session, Any, None]]:
    def _get_test_db():
        try:
            yield db
        finally:
            pass

    return _get_test_db


@pytest.fixture(scope="function")
def client(override_get_db) -> Generator:
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides = {}


@pytest.fixture
def mock_redis():
    class MockRedisClient:
        _storage = {}

        async def get(self, key):
            if key not in self._storage:
                return None
            value, _ = self._storage[key]
            return value

        async def set(self, key, value, expire=None):
            """Enhanced set method that handles Pydantic models"""
            try:
                # Handle Pydantic models
                if hasattr(value, "model_dump") and callable(value.model_dump):
                    # Pydantic v2+
                    value = value.model_dump()
                elif hasattr(value, "dict") and callable(value.dict):
                    # Pydantic v1
                    value = value.dict()
                
                self._storage[key] = (value, expire)
                return True
            except Exception as e:
                print(f"Error in mock redis set: {e}")
                return True

        async def delete(self, key):
            if key in self._storage:
                del self._storage[key]
            return True

        async def delete_pattern(self, pattern):
            pattern = pattern.rstrip("*")
            keys_to_delete = [k for k in self._storage.keys() if k.startswith(pattern)]
            for key in keys_to_delete:
                del self._storage[key]
            return len(keys_to_delete)

    return MockRedisClient()

@pytest.fixture
def override_get_redis(mock_redis):
    from app.utils.redis_cache import get_redis

    def _get_test_redis():
        return mock_redis

    app.dependency_overrides[get_redis] = _get_test_redis
    yield
    app.dependency_overrides = {}


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    user_data = {
        "email": "testuser@example.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        "is_admin": False,
        "is_verified": True,
    }

    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_admin(db: Session) -> User:
    """Create a test admin user"""
    admin_data = {
        "email": "admin@iwork.com",
        "hashed_password": get_password_hash("adminpassword"),
        "first_name": "Admin",
        "last_name": "User",
        "is_active": True,
        "is_admin": True,
        "is_verified": True,
    }

    admin = db.query(User).filter(User.email == admin_data["email"]).first()
    if not admin:
        admin = User(**admin_data)
        db.add(admin)
        db.commit()
        db.refresh(admin)
    else:
        admin.is_admin = True
        db.commit()
        db.refresh(admin)

    return admin


@pytest.fixture
def test_company(db: Session) -> Company:
    """Create a test company"""
    company_data = {
        "name": "Test Company, Inc.",
        "industry": "Technology",
        "location": "San Francisco, CA",
        "description": "A test company for automated tests",
        "website": "https://testcompany.example.com",
        "logo_url": "https://testcompany.example.com/logo.png",
        "founded_year": 2020,
        "is_public": True,
        "stock_symbol": "TSTC",
    }

    company = Company(**company_data)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@pytest.fixture
def test_review(db: Session, test_user: User, test_company: Company) -> Review:
    """Create a test review"""
    review_data = {
        "company_id": test_company.id,
        "user_id": test_user.id,
        "rating": 4.5,
        "employee_status": "FORMER",
        "employment_start_date": "2021-01-01",
        "employment_end_date": "2022-12-31",
        "pros": "Great team, good benefits, flexible hours",
        "cons": "Limited growth opportunities, bureaucratic processes",
        "recommendations": "Streamline decision making, improve career paths",
        "is_anonymous": False,
        "status": ReviewStatus.VERIFIED,
    }

    review = Review(**review_data)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@pytest.fixture
def test_salary(db: Session, test_user: User, test_company: Company) -> Salary:
    """Create a test salary entry"""
    salary_data = {
        "company_id": test_company.id,
        "user_id": test_user.id,
        "job_title": "Senior Software Engineer",
        "salary_amount": 150000.00,
        "currency": "USD",
        "experience_level": ExperienceLevel.SENIOR,
        "employment_type": EmploymentType.FULL_TIME,
        "location": "San Francisco, CA",
        "is_anonymous": True,
    }

    salary = Salary(**salary_data)
    db.add(salary)
    db.commit()
    db.refresh(salary)
    return salary


@pytest.fixture
def token_headers(client: TestClient, test_user: User) -> Dict[str, str]:
    """Create auth token headers for a regular user"""
    login_data = {
        "username": test_user.email,
        "password": "password123"
    }

    response = client.post("/auth/login", data=login_data)
    tokens = response.json()
    access_token = tokens["access_token"]

    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def admin_token_headers(client: TestClient, test_admin: User) -> Dict[str, str]:
    """Create auth token headers for an admin user"""
    login_data = {
        "username": test_admin.email,
        "password": "adminpassword"
    }

    response = client.post("/auth/login", data=login_data)
    tokens = response.json()
    access_token = tokens["access_token"]

    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture(scope="function")
async def async_client(override_get_db, override_get_redis) -> AsyncGenerator[AsyncClient, None]:
    from httpx import AsyncClient

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture(autouse=True)
def mock_email_verification():
    """
    Mock the email verification service to prevent database SSL issues during tests
    """
    with unittest.mock.patch("app.api.auth.send_verification_email", MockEmailService.send_verification_email), \
         unittest.mock.patch("app.api.auth.send_password_reset_email", MockEmailService.send_password_reset_email), \
         unittest.mock.patch("app.services.email.send_email", new_callable=AsyncMockSendEmail):
        yield
