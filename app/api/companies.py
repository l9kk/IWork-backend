from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.integrations import get_stock_api_service, get_tax_api_service
from app.db.base import get_db
from app import crud
from app.core.dependencies import get_current_user, get_current_admin_user
from app.models.user import User
from app.utils.redis_cache import RedisClient, get_redis
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse, CompanyDetail
from app.services.integrations.stock_api import StockAPIService
from app.services.integrations.tax_api import TaxAPIService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[CompanyResponse])
async def get_companies(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        skip: int = 0,
        limit: int = 100,
        name: Optional[str] = None,
        industry: Optional[str] = None,
        location: Optional[str] = None,
):
    # Create cache key based on parameters
    cache_key = f"companies:list:{skip}:{limit}:{name}:{industry}:{location}"

    # Try to get from cache
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    companies = crud.company.search(
        db,
        query=name if name else "",
        industry=industry,
        location=location,
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

    # Cache the result for 1 hour
    await redis.set(cache_key, result, expire=3600)

    return result


@router.post("/", response_model=CompanyResponse)
async def create_company(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        company_in: CompanyCreate,
        current_user: User = Depends(get_current_admin_user)
):
    company = crud.company.create(db, obj_in=company_in)

    # Invalidate cache
    await redis.delete_pattern("companies:list*")

    return company


@router.get("/{company_id}", response_model=CompanyDetail)
async def get_company(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        company_id: int,
        include_stock_data: bool = Query(False),
        include_tax_data: bool = Query(False),
        stock_service: StockAPIService = Depends(get_stock_api_service),
        tax_service: TaxAPIService = Depends(get_tax_api_service)
):
    cache_key = f"company:detail:{company_id}:{include_stock_data}:{include_tax_data}"

    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    company_data = crud.company.get_with_stats(db, id=company_id)
    if not company_data:
        raise HTTPException(status_code=404, detail="Company not found")

    company = company_data["company"]

    result = CompanyDetail(
        id=company.id,
        name=company.name,
        description=company.description,
        industry=company.industry,
        location=company.location,
        logo_url=company.logo_url,
        website=company.website,
        founded_year=company.founded_year,
        is_public=company.is_public,
        stock_symbol=company.stock_symbol if company.is_public else None,
        sec_cik=company.sec_cik,
        avg_rating=company_data["avg_rating"],
        review_count=company_data["review_count"]
    )

    if include_stock_data and company.is_public and company.stock_symbol:
        try:
            stock_data = await stock_service.get_stock_data(company.stock_symbol)
            result.stock_data = stock_data
        except Exception as e:
            logger.error(f"Error fetching stock data: {str(e)}")

    if include_tax_data:
        try:
            tax_data = await tax_service.get_company_tax_data(
                company_name=company.name,
                cik=company.sec_cik,
                symbol=company.stock_symbol if company.is_public else None
            )
            result.tax_data = tax_data
        except Exception as e:
            logger.error(f"Error fetching tax data: {str(e)}")

    await redis.set(cache_key, result, expire=3600)

    return result


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        company_id: int,
        company_in: CompanyUpdate,
        current_user: User = Depends(get_current_admin_user)
):
    company = crud.company.get(db, id=company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company = crud.company.update(db, db_obj=company, obj_in=company_in)

    await redis.delete(f"company:detail:{company_id}")
    await redis.delete_pattern("companies:list*")

    return company