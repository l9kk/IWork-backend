from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.company import Company
from app.models.review import Review
from app.models.review import ReviewStatus
from app.schemas.company import CompanyCreate, CompanyUpdate


class CRUDCompany(CRUDBase[Company, CompanyCreate, CompanyUpdate]):
    def search(
            self,
            db: Session,
            *,
            query: str = "",
            industry: Optional[str] = None,
            location: Optional[str] = None,
            skip: int = 0,
            limit: int = 100
    ) -> List[Company]:
        search_query = db.query(Company)

        if query:
            search_query = search_query.filter(Company.name.ilike(f"%{query}%"))

        if industry:
            search_query = search_query.filter(Company.industry.ilike(f"%{industry}%"))

        if location:
            search_query = search_query.filter(Company.location.ilike(f"%{location}%"))

        return search_query.offset(skip).limit(limit).all()

    def get_with_stats(self, db: Session, *, id: int) -> Optional[Dict[str, Any]]:
        company = db.query(Company).filter(Company.id == id).first()

        if not company:
            return None

        # Get review stats for verified reviews only
        review_stats = db.query(
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("review_count")
        ).filter(
            Review.company_id == id,
            Review.status == ReviewStatus.VERIFIED
        ).first()

        return {
            "company": company,
            "avg_rating": float(review_stats.avg_rating) if review_stats.avg_rating else 0.0,
            "review_count": review_stats.review_count
        }


company = CRUDCompany(Company)