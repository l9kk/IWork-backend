from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app import crud
from app.models.salary import ExperienceLevel, EmploymentType
from app.schemas.company import CompanyResponse
from app.schemas.review import ReviewResponse
from app.schemas.salary import SalaryResponse
from app.utils.redis_cache import RedisClient, get_redis

router = APIRouter()


@router.get("/companies", response_model=List[CompanyResponse])
async def search_companies(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        query: str,
        location: Optional[str] = None,
        industry: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
):
    cache_key = f"search:companies:{query}:{location}:{industry}:{skip}:{limit}"
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    companies = crud.company.search(
        db,
        query=query,
        location=location,
        industry=industry,
        skip=skip,
        limit=limit
    )

    result = [
        CompanyResponse(
            id=company.id,
            name=company.name,
            industry=company.industry,
            location=company.location,
            logo_url=company.logo_url
        )
        for company in companies
    ]

    # Cache for 15 minutes
    await redis.set(cache_key, result, expire=900)

    return result


@router.get("/reviews", response_model=List[ReviewResponse])
async def search_reviews(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        query: Optional[str] = None,
        company_id: Optional[int] = None,
        min_rating: Optional[float] = None,
        max_rating: Optional[float] = None,
        skip: int = 0,
        limit: int = 20
):
    cache_key = f"search:reviews:{query}:{company_id}:{min_rating}:{max_rating}:{skip}:{limit}"
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    reviews = crud.review.search_reviews(
        db,
        query=query,
        company_id=company_id,
        min_rating=min_rating,
        max_rating=max_rating,
        skip=skip,
        limit=limit
    )

    result = []
    for review in reviews:
        company = crud.company.get(db, id=review.company_id)
        company_name = company.name if company else "Unknown Company"

        # Handle anonymous reviews
        user_name = None
        if not review.is_anonymous:
            user = crud.user.get(db, id=review.user_id)
            if user:
                user_name = f"{user.first_name} {user.last_name}".strip() or "User"

        result.append(ReviewResponse(
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
            user_name=user_name
        ))

    # Cache for 15 minutes
    await redis.set(cache_key, result, expire=900)

    return result


@router.get("/salaries", response_model=List[SalaryResponse])
async def search_salaries(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        job_title: Optional[str] = None,
        company_id: Optional[int] = None,
        location: Optional[str] = None,
        experience_level: Optional[ExperienceLevel] = None,
        employment_type: Optional[EmploymentType] = None,
        min_salary: Optional[float] = None,
        max_salary: Optional[float] = None,
        skip: int = 0,
        limit: int = 20
):
    cache_key = f"search:salaries:{job_title}:{company_id}:{location}:{experience_level}:{employment_type}:{min_salary}:{max_salary}:{skip}:{limit}"
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    salaries = crud.salary.search_salaries(
        db,
        job_title=job_title,
        company_id=company_id,
        location=location,
        experience_level=experience_level,
        employment_type=employment_type,
        min_salary=min_salary,
        max_salary=max_salary,
        skip=skip,
        limit=limit
    )

    result = []
    for salary in salaries:
        company = crud.company.get(db, id=salary.company_id)
        company_name = company.name if company else "Unknown Company"

        result.append(SalaryResponse(
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

    # Cache for 15 minutes
    await redis.set(cache_key, result, expire=900)

    return result