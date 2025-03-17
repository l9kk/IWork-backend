from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app import crud
from app.models.salary import ExperienceLevel, EmploymentType
from app.models.user import User
from app.schemas.salary import SalaryCreate, SalaryUpdate, SalaryResponse, SalaryStatistics
from app.core.dependencies import get_current_user
from app.utils.redis_cache import RedisClient, get_redis

router = APIRouter()


@router.post("/", response_model=SalaryResponse)
async def create_salary(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        salary_in: SalaryCreate,
        current_user: User = Depends(get_current_user)
):
    company = crud.company.get(db, id=salary_in.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    salary = crud.salary.create_with_owner(db, obj_in=salary_in, user_id=current_user.id)

    # Invalidate cache
    await redis.delete_pattern(f"company:salaries:{salary.company_id}*")
    await redis.delete_pattern(f"salary:statistics:{salary.job_title}*")

    return SalaryResponse(
        id=salary.id,
        company_id=salary.company_id,
        company_name=company.name,
        job_title=salary.job_title,
        salary_amount=salary.salary_amount,
        currency=salary.currency,
        experience_level=salary.experience_level,
        employment_type=salary.employment_type,
        location=salary.location,
        created_at=salary.created_at
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
        limit: int = 50
):
    company = crud.company.get(db, id=company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    cache_key = f"company:salaries:{company_id}:{job_title}:{experience_level}:{employment_type}:{skip}:{limit}"
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    salaries = crud.salary.get_company_salaries(
        db,
        company_id=company_id,
        job_title=job_title,
        experience_level=experience_level,
        employment_type=employment_type,
        skip=skip,
        limit=limit
    )

    result = [
        SalaryResponse(
            id=salary.id,
            company_id=salary.company_id,
            company_name=company.name,
            job_title=salary.job_title,
            salary_amount=salary.salary_amount,
            currency=salary.currency,
            experience_level=salary.experience_level,
            employment_type=salary.employment_type,
            location=salary.location,
            created_at=salary.created_at
        )
        for salary in salaries
    ]

    # Cache for 1 hour
    await redis.set(cache_key, result, expire=3600)

    return result


@router.get("/statistics", response_model=List[SalaryStatistics])
async def get_salary_statistics(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        job_title: str,
        experience_level: Optional[ExperienceLevel] = None,
        location: Optional[str] = None
):
    cache_key = f"salary:statistics:{job_title}:{experience_level}:{location}"
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    statistics = crud.salary.get_salary_statistics(
        db,
        job_title=job_title,
        experience_level=experience_level,
        location=location
    )

    result = [
        SalaryStatistics(
            job_title=stat["job_title"],
            avg_salary=stat["avg_salary"],
            min_salary=stat["min_salary"],
            max_salary=stat["max_salary"],
            sample_size=stat["sample_size"],
            currency=stat["currency"]
        )
        for stat in statistics
    ]

    # Cache for 3 hours
    await redis.set(cache_key, result, expire=10800)

    return result


@router.get("/user/me", response_model=List[SalaryResponse])
async def get_my_salaries(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        skip: int = 0,
        limit: int = 50
):
    salaries = crud.salary.get_user_salaries(
        db, user_id=current_user.id, skip=skip, limit=limit
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

    return result


@router.put("/{salary_id}", response_model=SalaryResponse)
async def update_salary(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        salary_id: int,
        salary_in: SalaryUpdate,
        current_user: User = Depends(get_current_user)
):
    salary = crud.salary.get(db, id=salary_id)
    if not salary or salary.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Salary entry not found or not owned by user")

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
        experience_level=salary.experience_level,
        employment_type=salary.employment_type,
        location=salary.location,
        created_at=salary.created_at
    )