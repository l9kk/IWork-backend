from sqlalchemy.orm import Session

from app.models.company import Company


def test_company_model(db: Session, test_company: Company):
    """Test company model retrieval"""
    db_company = db.query(Company).filter(Company.id == test_company.id).first()

    assert db_company is not None
    assert db_company.name == "Test Company, Inc."
    assert db_company.industry == "Technology"
    assert db_company.location == "San Francisco, CA"
    assert db_company.is_public is True
    assert db_company.stock_symbol == "TSTC"