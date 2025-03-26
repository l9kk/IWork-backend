from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app import crud
from app.utils.redis_cache import RedisClient, get_redis
from app.services.search import SearchService
from app.schemas.company import CompanyResponse
from app.schemas.review import ReviewResponse
from app.schemas.salary import SalaryResponse
from pydantic import BaseModel

router = APIRouter()


class SearchResult(BaseModel):
    query: str
    skip: int
    limit: int
    total_counts: Dict[str, int]
    reviews: Optional[List[ReviewResponse]] = None
    companies: Optional[List[CompanyResponse]] = None
    salaries: Optional[List[SalaryResponse]] = None


@router.get("/fulltext", response_model=SearchResult)
async def full_text_search(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        query: str,
        entity_types: List[str] = Query(["reviews", "companies", "salaries"]),
        skip: int = 0,
        limit: int = 20
):
    """
    Perform full-text search across multiple entities.

    - query: Search query
    - entity_types: Types of entities to search ("reviews", "companies", "salaries")
    - skip: Number of results to skip for pagination
    - limit: Maximum number of results to return per entity type
    """

    cache_key = f"search:fulltext:{query}:{','.join(sorted(entity_types))}:{skip}:{limit}"

    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    search_result = SearchService.advanced_search(
        db, query, entity_types, skip, limit
    )

    response = {
        "query": query,
        "skip": skip,
        "limit": limit,
        "total_counts": search_result["total_counts"]
    }

    if "reviews" in search_result["results"]:
        reviews = []
        for review in search_result["results"]["reviews"]:
            company = crud.company.get(db, id=review.company_id)
            company_name = company.name if company else "Unknown Company"

            user_name = None
            if not review.is_anonymous:
                user = crud.user.get(db, id=review.user_id)
                if user:
                    user_name = f"{user.first_name} {user.last_name}".strip() or "User"

            highlight = None
            if review.pros:
                highlight = SearchService.get_search_highlights(review.pros, query)
            if not highlight and review.cons:
                highlight = SearchService.get_search_highlights(review.cons, query)
            if not highlight and review.recommendations:
                highlight = SearchService.get_search_highlights(review.recommendations, query)

            reviews.append(ReviewResponse(
                id=review.id,
                company_id=review.company_id,
                company_name=company_name,
                rating=review.rating,
                employee_status=review.employee_status,
                employment_start_date=review.employment_start_date,
                employment_end_date=review.employment_end_date,
                pros=review.pros,
                cons=review.cons,
                recommendations=review.recommendations,
                status=review.status,
                created_at=review.created_at,
                user_name=user_name,
                highlight=highlight
            ))

        response["reviews"] = reviews

    if "companies" in search_result["results"]:
        companies = []
        for company in search_result["results"]["companies"]:
            companies.append(CompanyResponse(
                id=company.id,
                name=company.name,
                industry=company.industry,
                location=company.location,
                logo_url=company.logo_url
            ))

        response["companies"] = companies

    if "salaries" in search_result["results"]:
        salaries = []
        for salary in search_result["results"]["salaries"]:
            company = crud.company.get(db, id=salary.company_id)
            company_name = company.name if company else "Unknown Company"

            salaries.append(SalaryResponse(
                id=salary.id,
                company_id=salary.company_id,
                company_name=company_name,
                job_title=salary.job_title,
                salary_amount=salary.salary_amount,
                currency=salary.currency,
                experience_level=salary.experience_level,
                employment_type=salary.employment_type,
                location=salary.location,
                created_at=salary.created_at
            ))

        response["salaries"] = salaries

    await redis.set(cache_key, response, expire=600)

    return response


@router.get("/companies", response_model=Dict[str, Any])
async def search_companies(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        query: str,
        industry: Optional[str] = None,
        location: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
):
    """
    Full-text search for companies with additional filters
    """

    cache_key = f"search:companies:{query}:{industry}:{location}:{skip}:{limit}"

    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    companies, total_count = SearchService.search_companies(
        db, query, industry, location, skip, limit
    )

    results = []
    for company in companies:
        highlight = None
        if company.description:
            highlight = SearchService.get_search_highlights(company.description, query)

        results.append({
            "id": company.id,
            "name": company.name,
            "industry": company.industry,
            "location": company.location,
            "logo_url": company.logo_url,
            "highlight": highlight
        })

    response = {
        "results": results,
        "total": total_count,
        "query": query,
        "skip": skip,
        "limit": limit
    }

    # Cache for 10 minutes
    await redis.set(cache_key, response, expire=600)

    return response