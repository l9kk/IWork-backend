from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app import crud
from app.utils.redis_cache import get_redis, RedisClient
from app.services.integrations.stock_api import StockAPIService
from app.services.integrations.tax_api import TaxAPIService
from app.schemas.integrations import (
    StockDataResponse,
    HistoricalStockDataResponse,
    TaxDataResponse,
)
from app.core.config import settings

router = APIRouter()


def get_stock_api_service(redis: RedisClient = Depends(get_redis)):
    return StockAPIService(redis_client=redis)


def get_tax_api_service(redis: RedisClient = Depends(get_redis)):
    alpha_vantage_api_key = getattr(settings, "ALPHA_VANTAGE_API_KEY", None)
    return TaxAPIService(
        redis_client=redis, alpha_vantage_api_key=alpha_vantage_api_key
    )


@router.get("/stock/{symbol}", response_model=StockDataResponse)
async def get_stock_data(
    symbol: str, stock_service: StockAPIService = Depends(get_stock_api_service)
):
    """
    Get current stock data for a company by stock symbol
    """
    return await stock_service.get_stock_data(symbol)


@router.get("/stock/{symbol}/historical", response_model=HistoricalStockDataResponse)
async def get_historical_stock_data(
    symbol: str,
    period: str = "1y",
    interval: str = "1mo",
    stock_service: StockAPIService = Depends(get_stock_api_service),
):
    """
    Get historical stock data for charting
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    """
    return await stock_service.get_historical_stock_data(symbol, period, interval)


@router.get("/taxes/company/{company_id}", response_model=TaxDataResponse)
async def get_company_tax_data(
    company_id: int,
    db: Session = Depends(get_db),
    tax_service: TaxAPIService = Depends(get_tax_api_service),
):
    """
    Get tax information for a company by ID
    """
    company = crud.company.get(db, id=company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        )

    cik = getattr(company, "sec_cik", None)
    symbol = company.stock_symbol if company.is_public else None

    return await tax_service.get_company_tax_data(
        company_name=company.name, cik=cik, symbol=symbol
    )


@router.get("/taxes/symbol/{symbol}", response_model=TaxDataResponse)
async def get_tax_data_by_symbol(
    symbol: str, tax_service: TaxAPIService = Depends(get_tax_api_service)
):
    """
    Get tax information for a public company by stock symbol
    """
    return await tax_service.get_company_tax_data(company_name=symbol, symbol=symbol)
