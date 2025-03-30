import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.review import Review, ReviewStatus
from app.models.company import Company
from app.models.salary import Salary

logger = logging.getLogger(__name__)


class SearchService:
    @staticmethod
    def search_reviews(
            db: Session,
            query: str,
            company_id: Optional[int] = None,
            min_rating: Optional[float] = None,
            max_rating: Optional[float] = None,
            skip: int = 0,
            limit: int = 20,
            status: ReviewStatus = ReviewStatus.VERIFIED
    ) -> Tuple[List[Review], int]:
        """
        Search reviews using full-text search
        Returns: (list of reviews, total count)
        """
        tsquery = func.plainto_tsquery('english', query)

        search_query = db.query(Review).filter(Review.status == status)

        if query and query.strip():
            search_query = search_query.filter(Review.search_vector.op('@@')(tsquery))

            search_query = search_query.order_by(
                func.ts_rank(Review.search_vector, tsquery).desc(),
                Review.created_at.desc()
            )
        else:
            search_query = search_query.order_by(Review.created_at.desc())

        if company_id:
            search_query = search_query.filter(Review.company_id == company_id)

        if min_rating is not None:
            search_query = search_query.filter(Review.rating >= min_rating)

        if max_rating is not None:
            search_query = search_query.filter(Review.rating <= max_rating)

        total_count = search_query.count()

        results = search_query.offset(skip).limit(limit).all()

        return results, total_count

    @staticmethod
    def search_companies(
            db: Session,
            query: str,
            industry: Optional[str] = None,
            location: Optional[str] = None,
            skip: int = 0,
            limit: int = 20
    ) -> Tuple[List[Company], int]:
        """
        Search companies using full-text search
        Returns: (list of companies, total count)
        """
        tsquery = func.plainto_tsquery('english', query)

        search_query = db.query(Company)

        if query and query.strip():
            search_query = search_query.filter(Company.search_vector.op('@@')(tsquery))

            search_query = search_query.order_by(
                func.ts_rank(Company.search_vector, tsquery).desc()
            )

        if industry:
            search_query = search_query.filter(Company.industry.ilike(f"%{industry}%"))

        if location:
            search_query = search_query.filter(Company.location.ilike(f"%{location}%"))

        total_count = search_query.count()

        results = search_query.offset(skip).limit(limit).all()

        return results, total_count

    @staticmethod
    def advanced_search(
            db: Session,
            query: str,
            entity_types: List[str] = ["reviews", "companies", "salaries"],
            skip: int = 0,
            limit: int = 20
    ) -> Dict[str, Any]:
        """
        Unified search across multiple entity types
        Returns: dictionary with search results by entity type
        """
        results = {}
        total_counts = {}

        if "reviews" in entity_types:
            review_results, review_count = SearchService.search_reviews(
                db, query, skip=skip, limit=limit
            )
            results["reviews"] = review_results
            total_counts["reviews"] = review_count

        if "companies" in entity_types:
            company_results, company_count = SearchService.search_companies(
                db, query, skip=skip, limit=limit
            )
            results["companies"] = company_results
            total_counts["companies"] = company_count

        if "salaries" in entity_types:
            salary_query = (
                db.query(Salary)
                .filter(or_(
                    Salary.job_title.ilike(f"%{query}%"),
                    Salary.location.ilike(f"%{query}%")
                ))
                .order_by(Salary.created_at.desc())
            )

            salary_count = salary_query.count()
            salary_results = salary_query.offset(skip).limit(limit).all()

            results["salaries"] = salary_results
            total_counts["salaries"] = salary_count

        return {
            "results": results,
            "total_counts": total_counts,
            "query": query,
            "skip": skip,
            "limit": limit
        }

    @staticmethod
    def get_search_highlights(text: str, query: str, max_length: int = 200) -> Optional[str]:
        """
        Generate search result highlights by extracting relevant snippets from text
        """
        if not text or not query:
            return None

        query_terms = [term.lower() for term in query.split() if len(term) > 2]

        if not query_terms:
            return text[:max_length] + ("..." if len(text) > max_length else "")

        text_lower = text.lower()

        positions = []
        for term in query_terms:
            pos = text_lower.find(term)
            while pos != -1:
                positions.append(pos)
                pos = text_lower.find(term, pos + 1)

        if not positions:
            return text[:max_length] + ("..." if len(text) > max_length else "")

        best_pos = min(positions)

        start_pos = max(0, best_pos - 50)

        if start_pos > 0:
            while start_pos > 0 and text[start_pos] != ' ':
                start_pos -= 1
            start_pos += 1

        highlight = text[start_pos:start_pos + max_length]

        if start_pos > 0:
            highlight = "..." + highlight
        if start_pos + max_length < len(text):
            highlight = highlight + "..."

        return highlight