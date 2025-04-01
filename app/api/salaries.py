from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.db.base import get_db
from app import crud
from app.models import Company
from app.models.salary import ExperienceLevel, EmploymentType, Salary
from app.models.user import User
from app.schemas.salary import (
    SalaryCreate,
    SalaryUpdate,
    SalaryResponse,
    SalaryStatistics,
    UserSalariesResponse,
)
from app.core.dependencies import get_current_user
from app.utils.redis_cache import RedisClient, get_redis
from app.services.salary_analytics import SalaryAnalyticsService

router = APIRouter()


@router.post("/", response_model=SalaryResponse)
async def create_salary(
    *,
    db: Session = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    salary_in: SalaryCreate,
    current_user: User = Depends(get_current_user),
):
    company = crud.company.get(db, id=salary_in.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    experience_level = getattr(salary_in.experience_level, "value", "intern").lower()
    employment_type = getattr(salary_in.employment_type, "value", "full-time").lower()

    result = db.execute(
        text(
            """
        INSERT INTO salaries 
        (user_id, company_id, job_title, salary_amount, currency, experience_level, employment_type, location, is_anonymous, created_at) 
        VALUES (:user_id, :company_id, :job_title, :salary_amount, :currency, :experience_level, :employment_type, :location, :is_anonymous, NOW())
        RETURNING id, created_at
        """
        ),
        {
            "user_id": current_user.id,
            "company_id": salary_in.company_id,
            "job_title": salary_in.job_title,
            "salary_amount": salary_in.salary_amount,
            "currency": salary_in.currency,
            "experience_level": experience_level,
            "employment_type": employment_type,
            "location": salary_in.location or "",
            "is_anonymous": salary_in.is_anonymous,
        },
    )

    row = result.fetchone()
    db.commit()

    await redis.delete_pattern(f"company:salaries:{salary_in.company_id}*")
    await redis.delete_pattern(f"salary:statistics:{salary_in.job_title}*")

    return SalaryResponse(
        id=row[0],
        company_id=salary_in.company_id,
        company_name=company.name,
        job_title=salary_in.job_title,
        salary_amount=salary_in.salary_amount,
        currency=salary_in.currency,
        experience_level=experience_level,
        employment_type=employment_type,
        location=salary_in.location,
        created_at=row[1],
    )


@router.get("/company/{company_id}", response_model=List[SalaryResponse])
async def get_company_salaries(
    *,
    db: Session = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    company_id: int,
    job_title: Optional[str] = None,
    experience_level: Optional[ExperienceLevel] = None,
    employment_type: Optional[EmploymentType] = None,
    skip: int = 0,
    limit: int = 50,
):

    cache_key = f"company_salaries:{company_id}:{hash((job_title, experience_level, employment_type, skip, limit))}"
    cached_result = await redis.get(cache_key)
    if cached_result:
        return [SalaryResponse(**item) for item in cached_result]

    company = crud.company.get(db, id=company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    salaries = crud.salary.get_company_salaries(
        db,
        company_id=company_id,
        job_title=job_title,
        experience_level=experience_level,
        employment_type=employment_type,
        skip=skip,
        limit=limit,
    )

    result = [
        SalaryResponse(
            id=salary.id,
            company_id=salary.company_id,
            company_name=company.name,
            job_title=salary.job_title,
            salary_amount=salary.salary_amount,
            currency=salary.currency,
            experience_level=ExperienceLevel(salary.experience_level.lower()),
            employment_type=EmploymentType(
                salary.employment_type.lower().replace("_", "-")
            ),
            location=salary.location,
            created_at=salary.created_at,
        )
        for salary in salaries
    ]

    dict_result = [item.model_dump() for item in result]
    # Cache for 1 hour
    await redis.set(cache_key, dict_result, expire=3600)
    return result


@router.get("/statistics", response_model=List[SalaryStatistics])
async def get_salary_statistics(
    *,
    db: Session = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    job_title: str,
    experience_level: Optional[ExperienceLevel] = None,
    location: Optional[str] = None,
):
    cache_key = f"salary:statistics:{job_title}:{experience_level}:{location}"
    cached_result = await redis.get(cache_key)
    if cached_result:
        return [SalaryStatistics(**item) for item in cached_result]

    statistics = crud.salary.get_salary_statistics(
        db, job_title=job_title, experience_level=experience_level, location=location
    )

    result = [
        SalaryStatistics(
            job_title=stat["job_title"],
            avg_salary=stat["avg_salary"],
            min_salary=stat["min_salary"],
            max_salary=stat["max_salary"],
            sample_size=stat["sample_size"],
            currency=stat["currency"],
        )
        for stat in statistics
    ]

    dict_result = [item.model_dump() for item in result]
    # Cache for 3 hours
    await redis.set(cache_key, dict_result, expire=10800)
    return result


@router.get("/analytics/compare", response_model=Dict[str, Any])
async def get_salary_comparison(
    *,
    db: Session = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    job_title: str,
    company_id: Optional[int] = None,
    location: Optional[str] = None,
    experience_level: Optional[ExperienceLevel] = None,
    employment_type: Optional[EmploymentType] = None,
    currency: str = "USD",
):
    """
    Get comparative salary analysis:
    - Company vs. industry averages
    - Location vs. national average
    """

    cache_key = f"salary:compare:{job_title}:{company_id}:{location}:{experience_level}:{employment_type}:{currency}"

    # Try to get from cache
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    result = SalaryAnalyticsService.get_comparative_analysis(
        db, job_title, company_id, location, experience_level, employment_type, currency
    )

    # Cache for 1 hour
    await redis.set(cache_key, result, expire=3600)

    return result


@router.get("/search", response_model=Dict[str, Any])
async def advanced_salary_search(
    *,
    db: Session = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    job_titles: List[str] = Query(..., description="Job titles to search for"),
    company_ids: Optional[List[int]] = Query(None),
    industries: Optional[List[str]] = Query(None),
    locations: Optional[List[str]] = Query(None),
    experience_levels: Optional[List[ExperienceLevel]] = Query(None),
    employment_types: Optional[List[EmploymentType]] = Query(None),
    currency: str = "USD",
    sort_by: str = "recency",
    skip: int = 0,
    limit: int = 20,
):
    """
    Advanced salary search with multiple selection filters and sorting options.
    """
    cache_key = (
        f"salary:search:{','.join(job_titles)}:{','.join([str(id) for id in company_ids or []])}:"
        f"{','.join(industries or [])}:{','.join(locations or [])}:"
        f"{','.join([level.value for level in experience_levels or []])}:"
        f"{','.join([type.value for type in employment_types or []])}:"
        f"{currency}:{sort_by}:{skip}:{limit}"
    )

    # Try to get from cache
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    salary_query = db.query(Salary)

    if job_titles:
        job_title_filters = []

        for title in job_titles:
            job_title_filters.append(Salary.job_title.ilike(f"%{title}%"))

        if job_title_filters:
            salary_query = salary_query.filter(or_(*job_title_filters))

    if company_ids and len(company_ids) > 0:
        salary_query = salary_query.filter(Salary.company_id.in_(company_ids))

    if industries and len(industries) > 0:
        salary_query = salary_query.join(Company, Salary.company_id == Company.id)
        industry_filters = []

        for industry in industries:
            industry_filters.append(Company.industry.ilike(f"%{industry}%"))

        salary_query = salary_query.filter(or_(*industry_filters))

    if locations and len(locations) > 0:
        location_filters = []

        for location in locations:
            location_filters.append(Salary.location.ilike(f"%{location}%"))

        salary_query = salary_query.filter(or_(*location_filters))

    if experience_levels and len(experience_levels) > 0:
        salary_query = salary_query.filter(
            Salary.experience_level.in_(experience_levels)
        )

    if employment_types and len(employment_types) > 0:
        salary_query = salary_query.filter(Salary.employment_type.in_(employment_types))

    salary_query = salary_query.filter(Salary.currency == currency)

    total_count = salary_query.count()

    if sort_by == "salary_high_to_low":
        salary_query = salary_query.order_by(Salary.salary_amount.desc())
    elif sort_by == "salary_low_to_high":
        salary_query = salary_query.order_by(Salary.salary_amount.asc())
    else:
        salary_query = salary_query.order_by(Salary.created_at.desc())

    salary_query = salary_query.offset(skip).limit(limit)

    salaries = salary_query.all()

    results = []

    for salary in salaries:
        company = crud.company.get(db, id=salary.company_id)
        company_name = company.name if company else "Unknown Company"

        results.append(
            {
                "id": salary.id,
                "company_id": salary.company_id,
                "company_name": company_name,
                "job_title": salary.job_title,
                "salary_amount": salary.salary_amount,
                "currency": salary.currency,
                "experience_level": salary.experience_level.value,
                "employment_type": salary.employment_type.value,
                "location": salary.location,
                "created_at": salary.created_at.isoformat(),
            }
        )

    response = {
        "results": results,
        "total": total_count,
        "filters_applied": {
            "job_titles": job_titles,
            "company_ids": company_ids,
            "industries": industries,
            "locations": locations,
            "experience_levels": (
                [level.value for level in experience_levels]
                if experience_levels
                else None
            ),
            "employment_types": (
                [type.value for type in employment_types] if employment_types else None
            ),
            "currency": currency,
        },
        "sort_by": sort_by,
        "skip": skip,
        "limit": limit,
    }

    # Cache for 15 minutes
    await redis.set(cache_key, response, expire=900)

    return response


@router.get("/user/me", response_model=UserSalariesResponse)
async def get_my_salaries(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
):
    total_count = db.query(Salary).filter(Salary.user_id == current_user.id).count()

    salaries = crud.salary.get_user_salaries(
        db, user_id=current_user.id, skip=skip, limit=limit
    )

    result = []
    for salary in salaries:
        company = crud.company.get(db, id=salary.company_id)
        company_name = company.name if company else "Unknown Company"

        result.append(
            SalaryResponse(
                id=salary.id,
                company_id=salary.company_id,
                company_name=company_name,
                job_title=salary.job_title,
                salary_amount=salary.salary_amount,
                currency=salary.currency,
                experience_level=ExperienceLevel(salary.experience_level.lower()),
                employment_type=EmploymentType(
                    salary.employment_type.lower().replace("_", "-")
                ),
                location=salary.location,
                created_at=salary.created_at,
            )
        )

    return UserSalariesResponse(total_count=total_count, salaries=result)


@router.put("/{salary_id}", response_model=SalaryResponse)
async def update_salary(
    *,
    db: Session = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    salary_id: int,
    salary_in: SalaryUpdate,
    current_user: User = Depends(get_current_user),
):
    salary = crud.salary.get(db, id=salary_id)
    if not salary or salary.user_id != current_user.id:
        raise HTTPException(
            status_code=404, detail="Salary entry not found or not owned by user"
        )

    salary = crud.salary.update(db, db_obj=salary, obj_in=salary_in)

    # Invalidate caches
    await redis.delete_pattern(f"company:salaries:{salary.company_id}*")
    await redis.delete_pattern(f"salary:statistics:{salary.job_title}*")

    company = crud.company.get(db, id=salary.company_id)
    company_name = company.name if company else "Unknown Company"

    return SalaryResponse(
        id=salary.id,
        company_id=salary.company_id,
        company_name=company_name,
        job_title=salary.job_title,
        salary_amount=salary.salary_amount,
        currency=salary.currency,
        experience_level=ExperienceLevel(salary.experience_level.lower()),
        employment_type=EmploymentType(
            salary.employment_type.lower().replace("_", "-")
        ),
        location=salary.location,
        created_at=salary.created_at,
    )
