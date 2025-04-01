import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from app.utils.redis_cache import RedisClient
from app.utils.formatters import format_currency

logger = logging.getLogger(__name__)


class TaxAPIService:
    def __init__(self, redis_client: RedisClient, alpha_vantage_api_key: str = None):
        self.redis_client = redis_client
        self.alpha_vantage_api_key = alpha_vantage_api_key
        self.sec_api_endpoint = "https://data.sec.gov/api/xbrl/companyfacts"
        self.headers = {
            "User-Agent": "IWork Application/1.0",
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }

    async def get_company_tax_data(
        self, company_name: str, cik: Optional[str] = None, symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get tax information for a company.
        For public companies, uses SEC EDGAR API and Alpha Vantage.
        For private companies, uses a simplified approach with estimates.

        Args:
            company_name: Name of the company
            cik: Central Index Key (SEC identifier for public companies)
            symbol: Stock symbol for public companies
        """
        is_public = bool(cik or symbol)

        # Generate cache key
        cache_key = f"tax_data:{cik or symbol or company_name}"
        cached_data = await self.redis_client.get(cache_key)

        if cached_data:
            return cached_data

        if is_public:
            try:
                if cik:
                    tax_data = await self._get_sec_tax_data(cik)
                    if tax_data and tax_data.get("yearly_taxes"):
                        await self.redis_client.set(cache_key, tax_data, expire=604800)
                        return tax_data

                if symbol and self.alpha_vantage_api_key:
                    tax_data = await self._get_alpha_vantage_tax_data(symbol)
                    if tax_data and tax_data.get("yearly_taxes"):
                        await self.redis_client.set(cache_key, tax_data, expire=604800)
                        return tax_data

            except Exception as e:
                logger.error(
                    f"Error fetching tax data for public company {company_name}: {str(e)}"
                )

        tax_data = self._generate_estimated_tax_data(company_name)

        # Cache for 24 hours (estimated data)
        await self.redis_client.set(cache_key, tax_data, expire=86400)

        return tax_data

    async def _get_sec_tax_data(self, cik: str) -> Dict[str, Any] | None:
        padded_cik = cik.zfill(10)

        try:
            url = f"{self.sec_api_endpoint}/CIK{padded_cik}.json"
            response = requests.get(url, headers=self.headers)

            if response.status_code != 200:
                logger.error(f"SEC API error: {response.status_code} - {response.text}")
                return None

            data = response.json()

            yearly_taxes = []

            if "facts" in data and "us-gaap" in data["facts"]:
                tax_fields = [
                    "IncomeTaxExpenseBenefit",
                    "CurrentIncomeTaxExpense",
                    "ProvisionForIncomeTaxes",
                ]

                for field in tax_fields:
                    if field in data["facts"]["us-gaap"]:
                        tax_data = data["facts"]["us-gaap"][field]

                        if "USD" in tax_data["units"]:
                            for entry in tax_data["units"]["USD"]:
                                if "fy" in entry and "val" in entry:
                                    year = entry["fy"]
                                    value = entry["val"]

                                    if year:
                                        yearly_taxes.append(
                                            {
                                                "year": year,
                                                "amount": value,
                                                "formatted_amount": format_currency(
                                                    value
                                                ),
                                                "source": "SEC EDGAR",
                                            }
                                        )

                        if yearly_taxes:
                            break

            yearly_taxes.sort(key=lambda x: x["year"], reverse=True)

            yearly_taxes = yearly_taxes[:5]

            return {
                "company_name": data.get("entityName", "Unknown"),
                "cik": cik,
                "yearly_taxes": yearly_taxes,
                "data_source": "SEC EDGAR",
                "retrieved_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error fetching SEC tax data for {cik}: {str(e)}")
            return None

    async def _get_alpha_vantage_tax_data(self, symbol: str) -> Dict[str, Any] | None:
        if not self.alpha_vantage_api_key:
            return None

        try:
            url = f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={symbol}&apikey={self.alpha_vantage_api_key}"
            response = requests.get(url)

            if response.status_code != 200:
                logger.error(
                    f"Alpha Vantage API error: {response.status_code} - {response.text}"
                )
                return None

            data = response.json()

            if "annualReports" not in data:
                return None

            yearly_taxes = []

            for report in data["annualReports"]:
                if "fiscalDateEnding" in report and "incomeTaxExpense" in report:
                    year = report["fiscalDateEnding"][:4]  # Extract year from date
                    tax_expense = report["incomeTaxExpense"]

                    if tax_expense and tax_expense != "None":
                        tax_expense = float(tax_expense)
                        yearly_taxes.append(
                            {
                                "year": year,
                                "amount": tax_expense,
                                "formatted_amount": format_currency(tax_expense),
                                "source": "Alpha Vantage",
                            }
                        )

            yearly_taxes.sort(key=lambda x: x["year"], reverse=True)

            return {
                "company_name": data.get("symbol", symbol),
                "symbol": symbol,
                "yearly_taxes": yearly_taxes,
                "data_source": "Alpha Vantage",
                "retrieved_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(
                f"Error fetching Alpha Vantage tax data for {symbol}: {str(e)}"
            )
            return None

    def _generate_estimated_tax_data(self, company_name: str) -> Dict[str, Any]:
        """
        Generate estimated tax data for companies when real data is not available.
        This is useful for private companies or when API calls fail.
        """
        import hashlib
        import random

        name_hash = int(hashlib.md5(company_name.encode()).hexdigest(), 16)
        random.seed(name_hash)

        current_year = datetime.now().year

        yearly_taxes = []
        base_amount = random.randint(100_000, 10_000_000)

        for i in range(5):
            year = current_year - i

            variation = random.uniform(0.8, 1.2)
            tax_amount = base_amount * variation * (1.05**i)

            yearly_taxes.append(
                {
                    "year": str(year),
                    "amount": round(tax_amount, 2),
                    "formatted_amount": format_currency(tax_amount),
                    "source": "Estimated",
                }
            )

        return {
            "company_name": company_name,
            "yearly_taxes": yearly_taxes,
            "data_source": "Estimated (real data not available)",
            "retrieved_at": datetime.now().isoformat(),
            "note": "These tax figures are estimated and may not reflect actual financial data.",
        }
