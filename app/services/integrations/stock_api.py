import logging
from typing import Dict, Any
from datetime import datetime
import yfinance as yf

from fastapi import HTTPException, status
from app.utils.redis_cache import RedisClient

logger = logging.getLogger(__name__)


class StockAPIService:
    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client

    async def get_stock_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get stock data for a company by its stock symbol.
        Uses cache to avoid excessive API calls.
        """
        # Check cache first
        cache_key = f"stock_data:{symbol}"
        cached_data = await self.redis_client.get(cache_key)

        if cached_data:
            return cached_data

        try:
            # Fetch data from Yahoo Finance
            stock = yf.Ticker(symbol)

            # Get basic info
            info = stock.info

            # Extract relevant data
            stock_data = {
                "symbol": symbol,
                "company_name": info.get("shortName", "Unknown"),
                "current_price": info.get("currentPrice", None),
                "previous_close": info.get("previousClose", None),
                "open": info.get("open", None),
                "day_high": info.get("dayHigh", None),
                "day_low": info.get("dayLow", None),
                "volume": info.get("volume", None),
                "market_cap": info.get("marketCap", None),
                "pe_ratio": info.get("trailingPE", None),
                "dividend_yield": info.get("dividendYield", None) if info.get("dividendYield") else None,
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh", None),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow", None),
                "timestamp": datetime.now().isoformat(),
                "currency": info.get("currency", "USD")
            }

            # Get recent price change data (1 day)
            if stock_data["current_price"] and stock_data["previous_close"]:
                price_change = stock_data["current_price"] - stock_data["previous_close"]
                price_change_percent = (price_change / stock_data["previous_close"]) * 100
                stock_data["price_change"] = round(price_change, 2)
                stock_data["price_change_percent"] = round(price_change_percent, 2)
            else:
                stock_data["price_change"] = None
                stock_data["price_change_percent"] = None

            # Format price with currency
            if stock_data["current_price"]:
                stock_data["formatted_price"] = f"{stock_data['current_price']:.2f} {stock_data['currency']}"
            else:
                stock_data["formatted_price"] = "N/A"

            # Add formatted market cap
            if stock_data["market_cap"]:
                stock_data["formatted_market_cap"] = self._format_large_number(stock_data["market_cap"])
            else:
                stock_data["formatted_market_cap"] = "N/A"

            # Cache the results for 30 minutes
            await self.redis_client.set(cache_key, stock_data, expire=1800)

            return stock_data

        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch stock data: {str(e)}"
            )

    async def get_historical_stock_data(
            self, symbol: str, period: str = "1y", interval: str = "1mo"
    ) -> Dict[str, Any]:
        """
        Get historical stock data for charting.
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        """
        # Check cache first
        cache_key = f"stock_historical:{symbol}:{period}:{interval}"
        cached_data = await self.redis_client.get(cache_key)

        if cached_data:
            return cached_data

        try:
            # Fetch historical data
            stock = yf.Ticker(symbol)
            history = stock.history(period=period, interval=interval)

            # Convert to a list of data points for charting
            data_points = []
            for date, row in history.iterrows():
                data_points.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "open": round(row['Open'], 2),
                    "high": round(row['High'], 2),
                    "low": round(row['Low'], 2),
                    "close": round(row['Close'], 2),
                    "volume": row['Volume']
                })

            result = {
                "symbol": symbol,
                "period": period,
                "interval": interval,
                "data": data_points,
                "timestamp": datetime.now().isoformat()
            }

            # Cache the results for 24 hours
            await self.redis_client.set(cache_key, result, expire=86400)

            return result

        except Exception as e:
            logger.error(f"Error fetching historical stock data for {symbol}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch historical stock data: {str(e)}"
            )

    def _format_large_number(self, number: float) -> str:
        """Format large numbers in a human-readable way (e.g., 1.2B, 345.6M)"""
        if number >= 1_000_000_000:
            return f"{number / 1_000_000_000:.1f}B"
        elif number >= 1_000_000:
            return f"{number / 1_000_000:.1f}M"
        elif number >= 1_000:
            return f"{number / 1_000:.1f}K"
        else:
            return str(number)