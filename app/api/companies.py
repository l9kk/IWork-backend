from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, distinct, and_, or_
from sqlalchemy.orm import Session

from app.api.integrations import get_stock_api_service, get_tax_api_service
from app.db.base import get_db
from app import crud
from app.core.dependencies import get_current_user, get_current_admin_user
from app.models import Company, Review, Salary
from app.models.review import ReviewStatus
from app.models.user import User
from app.services.search import SearchService
from app.utils.redis_cache import RedisClient, get_redis
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse, CompanyDetail, CompanyFinancials
from app.services.integrations.stock_api import StockAPIService
from app.services.integrations.tax_api import TaxAPIService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=Dict[str, Any])
async def get_companies(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        company_name: Optional[str] = None,
        job_title: Optional[str] = None,
        industries: Optional[List[str]] = Query(None),
        locations: Optional[List[str]] = Query(None),
        min_rating: Optional[float] = None,
        sort_by: str = "relevance",
        autocomplete: bool = False,
        skip: int = 0,
        limit: int = 100,
):
    """
    Unified company search endpoint with real-time autocomplete and advanced filtering.
    
    - company_name: Search term for company name with optional autocomplete
    - job_title: Search term for job titles within companies
    - autocomplete: Enable autocomplete mode for real-time suggestions
    - industries: Filter by industries
    - locations: Filter by locations (cities)
    - min_rating: Filter by minimum company rating
    - sort_by: Sort results by relevance, rating, etc.
    - skip, limit: Pagination parameters
    """
    # Create cache key based on parameters
    cache_key = (
        f"companies:unified:v2:{company_name}:{job_title}:{','.join(industries or [])}:{','.join(locations or [])}:"
        f"{min_rating}:{sort_by}:{autocomplete}:{skip}:{limit}"
    )

    # Try to get from cache
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    # Subquery to count salaries for each company
    salary_count_subquery = db.query(
        Salary.company_id,
        func.count(distinct(Salary.id)).label("salary_count")
    ).group_by(Salary.company_id).subquery()

    # Base query joining with reviews for rating filters and counts, and salaries for salary counts
    company_query = db.query(
        Company,
        func.coalesce(func.avg(Review.rating), 0).label("avg_rating"),
        func.count(distinct(Review.id)).label("review_count"),
        func.coalesce(salary_count_subquery.c.salary_count, 0).label("salary_count")
    ).outerjoin(
        Review, and_(
            Company.id == Review.company_id,
            Review.status == ReviewStatus.VERIFIED
        )
    ).outerjoin(
        salary_count_subquery, Company.id == salary_count_subquery.c.company_id
    ).group_by(Company.id, salary_count_subquery.c.salary_count)
    
    # Handle company name search with autocomplete if needed
    if company_name and company_name.strip():
        if autocomplete:
            # For autocomplete, use prefix matching (ILIKE with trailing %)
            company_query = company_query.filter(Company.name.ilike(f"{company_name}%"))
        else:
            # For regular search, use full-text search
            tsquery = func.plainto_tsquery('english', company_name)
            company_query = company_query.filter(Company.search_vector.op('@@')(tsquery))
    
    # Handle job title search by joining with Salary table
    if job_title and job_title.strip():
        job_title_subquery = db.query(
            Salary.company_id
        ).filter(
            Salary.job_title.ilike(f"%{job_title}%") if not autocomplete else Salary.job_title.ilike(f"{job_title}%")
        ).distinct().subquery()
        
        company_query = company_query.join(
            job_title_subquery,
            Company.id == job_title_subquery.c.company_id
        )
    
    # Apply industry filters
    if industries and len(industries) > 0:
        industry_filters = []
        for industry in industries:
            industry_filters.append(Company.industry.ilike(f"%{industry}%"))
        company_query = company_query.filter(or_(*industry_filters))

    # Apply location filters
    if locations and len(locations) > 0:
        location_filters = []
        for location in locations:
            location_filters.append(Company.location.ilike(f"%{location}%"))
        company_query = company_query.filter(or_(*location_filters))

    # Apply rating filter
    if min_rating is not None:
        company_query = company_query.having(func.coalesce(func.avg(Review.rating), 0) >= min_rating)

    # Get total count before pagination
    count_query = company_query.subquery()
    total_count = db.query(func.count()).select_from(count_query).scalar()

    # Apply sorting
    if sort_by == "relevance" and company_name and company_name.strip() and not autocomplete:
        tsquery = func.plainto_tsquery('english', company_name)
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
        # Default sorting for autocomplete results is by name
        if autocomplete:
            company_query = company_query.order_by(Company.name.asc())
        else:
            company_query = company_query.order_by(Company.name.asc())

    # Apply pagination
    company_query = company_query.offset(skip).limit(limit)
    query_results = company_query.all()

    # Format results
    results = []
    for company, avg_rating, review_count, salary_count in query_results:
        highlight = None
        if company_name and company_name.strip() and company.description and not autocomplete:
            highlight = SearchService.get_search_highlights(company.description, company_name)

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
            "salary_count": int(salary_count),
            "highlight": highlight
        })

    response = {
        "results": results,
        "total": total_count or 0,
        "filters_applied": {
            "company_name": company_name,
            "job_title": job_title,
            "industries": industries,
            "locations": locations,
            "min_rating": min_rating,
            "autocomplete": autocomplete
        },
        "sort_by": sort_by,
        "skip": skip,
        "limit": limit
    }

    cache_duration = 300 if autocomplete else 900  # 5 minutes for autocomplete, 15 minutes for regular searches
    await redis.set(cache_key, response, expire=cache_duration)

    return response


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
        tax_service: TaxAPIService = Depends(get_tax_api_service)
):
    cache_key = f"company:detail:{company_id}"
    await redis.delete(cache_key)

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
        review_count=company_data["review_count"],
        annual_revenue=None,
        annual_revenue_formatted=None 
    )

    try:
        logger.info(f"Fetching tax data for company {company_id} to calculate revenue")
        tax_data = await tax_service.get_company_tax_data(
            company_name=company.name,
            cik=company.sec_cik,
            symbol=company.stock_symbol if company.is_public else None
        )
        
        logger.info(f"Tax data received: {bool(tax_data)} with yearly taxes: {bool(tax_data and tax_data.get('yearly_taxes'))}")
        
        if tax_data and tax_data.get("yearly_taxes") and len(tax_data.get("yearly_taxes")) > 0:
            most_recent_tax = tax_data["yearly_taxes"][0]
            tax_amount = most_recent_tax.get("amount", 0)
            
            logger.info(f"Using tax amount {tax_amount} from year {most_recent_tax.get('year')} to calculate revenue")
            estimated_revenue = tax_amount * 4 * 6.67
            
            result.annual_revenue = estimated_revenue
            result.annual_revenue_formatted = _format_currency(estimated_revenue)
            logger.info(f"Calculated annual revenue: {result.annual_revenue_formatted}")
        else:
            logger.warning(f"No yearly tax data available for company {company_id}")
    except Exception as e:
        logger.error(f"Error fetching tax data for revenue calculation: {str(e)}")
        result.annual_revenue = 0
        result.annual_revenue_formatted = "$0.00"

    random_review = db.query(Review).filter(
        Review.company_id == company_id,
        Review.status == ReviewStatus.VERIFIED
    ).order_by(func.random()).first()
    
    if random_review:
        user_name = None
        if not random_review.is_anonymous:
            user = crud.user.get(db, id=random_review.user_id)
            if user:
                user_name = f"{user.first_name} {user.last_name}".strip() or "User"
                
        result.random_review = {
            "id": random_review.id,
            "company_id": random_review.company_id,
            "company_name": company.name,
            "rating": random_review.rating,
            "employee_status": random_review.employee_status,
            "employment_start_date": random_review.employment_start_date,
            "employment_end_date": random_review.employment_end_date,
            "pros": random_review.pros,
            "cons": random_review.cons,
            "recommendations": random_review.recommendations,
            "status": random_review.status,
            "created_at": random_review.created_at,
            "user_name": user_name
        }

    if company.industry:
        competitors = db.query(Company).filter(
            Company.industry == company.industry,
            Company.id != company.id
        ).order_by(func.random()).limit(5).all()
        
        result.competitors = [
            CompanyResponse(
                id=comp.id,
                name=comp.name,
                industry=comp.industry,
                location=comp.location,
                logo_url=comp.logo_url
            ) for comp in competitors
        ]
    
    avg_ratings_subquery = db.query(
        Review.company_id,
        func.avg(Review.rating).label("avg_rating"),
        func.count(Review.id).label("review_count")
    ).filter(
        Review.status == ReviewStatus.VERIFIED
    ).group_by(Review.company_id).subquery()
    
    recommended_query = db.query(
        Company,
        avg_ratings_subquery.c.avg_rating,
        avg_ratings_subquery.c.review_count
    ).join(
        avg_ratings_subquery,
        Company.id == avg_ratings_subquery.c.company_id,
        isouter=True
    ).filter(
        Company.id != company_id
    )
    
    if company.location:
        location_term = company.location.split(',')[0]
        recommended_query = recommended_query.filter(
            Company.location.ilike(f"%{location_term}%")
        )
    
    recommended_companies = recommended_query.order_by(func.random()).limit(5).all()
    
    if len(recommended_companies) < 3 and company_data["avg_rating"] > 0:
        similar_rating_query = db.query(
            Company,
            avg_ratings_subquery.c.avg_rating,
            avg_ratings_subquery.c.review_count
        ).join(
            avg_ratings_subquery,
            Company.id == avg_ratings_subquery.c.company_id
        ).filter(
            Company.id != company_id,
            Company.id.notin_([c[0].id for c in recommended_companies]),
            func.abs(avg_ratings_subquery.c.avg_rating - company_data["avg_rating"]) < 1.0
        ).order_by(func.random())
        
        additional_companies = similar_rating_query.limit(3 - len(recommended_companies)).all()
        recommended_companies.extend(additional_companies)
    
    result.recommended_companies = []
    for comp, avg_rating, review_count in recommended_companies:
        result.recommended_companies.append({
            "id": comp.id,
            "name": comp.name,
            "logo_url": comp.logo_url,
            "avg_rating": float(avg_rating) if avg_rating is not None else 0.0,
            "review_count": review_count or 0
        })

    await redis.set(cache_key, result, expire=3600)

    return result


@router.get("/{company_id}/financials", response_model=CompanyFinancials)
async def get_company_financials(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        company_id: int,
        include_industry_comparison: bool = Query(False),
        include_historical_data: bool = Query(False),
        stock_service: StockAPIService = Depends(get_stock_api_service),
        tax_service: TaxAPIService = Depends(get_tax_api_service)
):
    """
    Get detailed financial information about a company including:
    - Revenue and tax data
    - Stock information (for public companies)
    - Key financial ratios
    - Industry comparisons (optional)
    - Historical financial data (optional)
    """
    cache_key = f"company:financials:{company_id}:{include_industry_comparison}:{include_historical_data}"

    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    company = crud.company.get(db, id=company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    result = CompanyFinancials(
        id=company.id,
        name=company.name,
        is_public=company.is_public,
        stock_symbol=company.stock_symbol if company.is_public else None,
        sec_cik=company.sec_cik,
        industry=company.industry,
    )

    if company.is_public and company.stock_symbol:
        try:
            stock_data = await stock_service.get_stock_data(company.stock_symbol)
            result.stock_data = stock_data
            
            if include_historical_data:
                historical_data = await stock_service.get_historical_stock_data(
                    company.stock_symbol, period="1y", interval="1mo"
                )
                result.historical_stock_data = historical_data
                
        except Exception as e:
            logger.error(f"Error fetching stock data: {str(e)}")

    try:
        tax_data = await tax_service.get_company_tax_data(
            company_name=company.name,
            cik=company.sec_cik,
            symbol=company.stock_symbol if company.is_public else None
        )
        
        result.tax_data = tax_data
        
        if tax_data and tax_data.get("yearly_taxes") and len(tax_data.get("yearly_taxes")) > 0:
            most_recent_tax = tax_data["yearly_taxes"][0]
            tax_amount = most_recent_tax.get("amount", 0)
            
            estimated_revenue = tax_amount * 4 * 6.67
            
            result.annual_revenue = estimated_revenue
            result.annual_revenue_formatted = _format_currency(estimated_revenue)
            
            if len(tax_data.get("yearly_taxes")) > 1:
                revenue_trend = []
                for tax_entry in tax_data.get("yearly_taxes"):
                    year_tax = tax_entry.get("amount", 0)
                    year_revenue = year_tax * 4 * 6.67
                    revenue_trend.append({
                        "year": tax_entry.get("year"),
                        "revenue": year_revenue,
                        "revenue_formatted": _format_currency(year_revenue)
                    })
                result.revenue_trend = revenue_trend
            
    except Exception as e:
        logger.error(f"Error fetching tax data: {str(e)}")

    if include_industry_comparison and company.industry:
        try:
            industry_companies = db.query(Company).filter(
                Company.industry == company.industry,
                Company.id != company.id,
                Company.is_public == True
            ).limit(5).all()
            
            industry_data = []
            for comp in industry_companies:
                comp_data = {
                    "id": comp.id,
                    "name": comp.name,
                    "stock_symbol": comp.stock_symbol
                }
                
                if comp.stock_symbol:
                    try:
                        stock_info = await stock_service.get_stock_data(comp.stock_symbol)
                        comp_data.update({
                            "market_cap": stock_info.get("market_cap"),
                            "market_cap_formatted": stock_info.get("formatted_market_cap"),
                            "pe_ratio": stock_info.get("pe_ratio"),
                            "dividend_yield": stock_info.get("dividend_yield")
                        })
                    except Exception:
                        pass
                
                industry_data.append(comp_data)
            
            result.industry_comparison = industry_data
            
        except Exception as e:
            logger.error(f"Error creating industry comparison: {str(e)}")

    if company.is_public and company.stock_symbol and result.stock_data:
        result.key_metrics = {
            "market_cap": result.stock_data.get("market_cap"),
            "market_cap_formatted": result.stock_data.get("formatted_market_cap"),
            "pe_ratio": result.stock_data.get("pe_ratio"),
            "dividend_yield": result.stock_data.get("dividend_yield"),
            "fifty_two_week_high": result.stock_data.get("fifty_two_week_high"),
            "fifty_two_week_low": result.stock_data.get("fifty_two_week_low")
        }

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

def _format_currency(amount: float) -> str:
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.2f} billion"
    elif amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f} million"
    elif amount >= 1_000:
        return f"${amount / 1_000:.2f} thousand"
    else:
        return f"${amount:.2f}"