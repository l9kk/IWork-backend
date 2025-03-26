from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, distinct, and_, or_
from sqlalchemy.orm import Session

from app.api.integrations import get_stock_api_service, get_tax_api_service
from app.db.base import get_db
from app import crud
from app.core.dependencies import get_current_user, get_current_admin_user
from app.models import Company, Review
from app.models.review import ReviewStatus
from app.models.user import User
from app.services.search import SearchService
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


@router.get("/search", response_model=Dict[str, Any])
async def company_search(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        query: Optional[str] = None,
        industries: Optional[List[str]] = Query(None),
        locations: Optional[List[str]] = Query(None),
        founding_years: Optional[List[int]] = Query(None),
        is_public: Optional[bool] = None,
        min_rating: Optional[float] = None,
        max_rating: Optional[float] = None,
        sort_by: str = "relevance",
        skip: int = 0,
        limit: int = 20
):
    """
    Advanced company search with multiple selection filters and sorting options
    """

    cache_key = (
        f"company:advanced:{query}:{','.join(industries or [])}:{','.join(locations or [])}:"
        f"{','.join([str(y) for y in founding_years or []])}:{is_public}:"
        f"{min_rating}:{max_rating}:{sort_by}:{skip}:{limit}"
    )

    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    company_query = db.query(
        Company,
        func.coalesce(func.avg(Review.rating), 0).label("avg_rating"),
        func.count(distinct(Review.id)).label("review_count")
    ).outerjoin(
        Review, and_(
            Company.id == Review.company_id,
            Review.status == ReviewStatus.VERIFIED
        )
    ).group_by(Company.id)

    if query and query.strip():
        tsquery = func.plainto_tsquery('english', query)
        company_query = company_query.filter(Company.search_vector.op('@@')(tsquery))

    if industries and len(industries) > 0:
        industry_filters = []
        for industry in industries:
            industry_filters.append(Company.industry.ilike(f"%{industry}%"))
        company_query = company_query.filter(or_(*industry_filters))

    if locations and len(locations) > 0:
        location_filters = []
        for location in locations:
            location_filters.append(Company.location.ilike(f"%{location}%"))
        company_query = company_query.filter(or_(*location_filters))

    if founding_years and len(founding_years) > 0:
        company_query = company_query.filter(Company.founded_year.in_(founding_years))

    if is_public is not None:
        company_query = company_query.filter(Company.is_public == is_public)

    if min_rating is not None:
        company_query = company_query.having(func.coalesce(func.avg(Review.rating), 0) >= min_rating)

    if max_rating is not None:
        company_query = company_query.having(func.coalesce(func.avg(Review.rating), 0) <= max_rating)

    count_query = company_query.subquery()
    total_count = db.query(func.count()).select_from(count_query).scalar()

    if sort_by == "relevance" and query and query.strip():
        tsquery = func.plainto_tsquery('english', query)
        company_query = company_query.order_by(
            func.ts_rank(Company.search_vector, tsquery).desc()
        )
    elif sort_by == "rating_high_to_low":
        company_query = company_query.order_by(
            func.coalesce(func.avg(Review.rating), 0).desc(),
            func.count(Review.id).desc()
        )
    elif sort_by == "review_count":
        company_query = company_query.order_by(
            func.count(Review.id).desc(),
            func.coalesce(func.avg(Review.rating), 0).desc()
        )
    elif sort_by == "name_asc":
        company_query = company_query.order_by(Company.name.asc())
    else:
        company_query = company_query.order_by(Company.name.asc())

    company_query = company_query.offset(skip).limit(limit)

    query_results = company_query.all()

    results = []
    for company, avg_rating, review_count in query_results:
        highlight = None
        if query and query.strip() and company.description:
            highlight = SearchService.get_search_highlights(company.description, query)

        results.append({
            "id": company.id,
            "name": company.name,
            "industry": company.industry,
            "location": company.location,
            "logo_url": company.logo_url,
            "is_public": company.is_public,
            "stock_symbol": company.stock_symbol if company.is_public else None,
            "founded_year": company.founded_year,
            "avg_rating": float(avg_rating),
            "review_count": review_count,
            "highlight": highlight
        })

    response = {
        "results": results,
        "total": total_count or 0,
        "filters_applied": {
            "query": query,
            "industries": industries,
            "locations": locations,
            "founding_years": founding_years,
            "is_public": is_public,
            "min_rating": min_rating,
            "max_rating": max_rating
        },
        "sort_by": sort_by,
        "skip": skip,
        "limit": limit
    }

    # Cache for 15 minutes
    await redis.set(cache_key, response, expire=900)

    return response

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