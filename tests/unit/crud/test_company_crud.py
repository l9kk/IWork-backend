from sqlalchemy.orm import Session

from app import crud
from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyUpdate


def test_create_company(db: Session):
    """Test creating a new company"""
    company_in = CompanyCreate(
        name="New Test Company",
        industry="Finance",
        location="New York, NY",
        description="A new test company",
        website="https://newtestcompany.example.com",
        founded_year=2019,
        is_public=False
    )

    company = crud.company.create(db, obj_in=company_in)

    assert company.name == "New Test Company"
    assert company.industry == "Finance"
    assert company.location == "New York, NY"
    assert company.is_public is False
    assert company.stock_symbol is None


def test_get_company(db: Session, test_company: Company):
    """Test retrieving a company by ID"""
    company = crud.company.get(db, id=test_company.id)

    assert company is not None
    assert company.id == test_company.id
    assert company.name == test_company.name


def test_update_company(db: Session, test_company: Company):
    """Test updating a company"""
    company_update = CompanyUpdate(
        description="Updated company description",
        founded_year=2018
    )

    updated_company = crud.company.update(db, db_obj=test_company, obj_in=company_update)

    assert updated_company.description == "Updated company description"
    assert updated_company.founded_year == 2018
    assert updated_company.name == test_company.name


def test_search_companies(db: Session, test_company: Company):
    """Test searching companies by name, industry, or location"""
    company_in = CompanyCreate(
        name="Another Tech Co",
        industry="Technology",
        location="Austin, TX",
        description="Another test company",
        is_public=False
    )
    crud.company.create(db, obj_in=company_in)

    tech_companies = crud.company.search(db, industry="Technology")
    assert len(tech_companies) == 2

    test_companies = crud.company.search(db, query="Test")
    assert len(test_companies) == 1
    assert test_companies[0].id == test_company.id

    sf_companies = crud.company.search(db, location="San Francisco")
    assert len(sf_companies) == 1
    assert sf_companies[0].id == test_company.id