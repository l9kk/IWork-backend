import logging
import statistics
from typing import Dict, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.salary import Salary, ExperienceLevel, EmploymentType
from app.models.company import Company

logger = logging.getLogger(__name__)


class SalaryAnalyticsService:
    @staticmethod
    def get_detailed_salary_breakdown(
            db: Session,
            job_title: Optional[str] = None,
            company_id: Optional[int] = None,
            industry: Optional[str] = None,
            location: Optional[str] = None,
            currency: str = "USD"
    ) -> Dict[str, Any]:
        base_query = db.query(Salary).filter(Salary.currency == currency)

        if job_title:
            base_query = base_query.filter(Salary.job_title.ilike(f"%{job_title}%"))

        if company_id:
            base_query = base_query.filter(Salary.company_id == company_id)

        if location:
            base_query = base_query.filter(Salary.location.ilike(f"%{location}%"))

        if industry:
            base_query = base_query.join(Company, Salary.company_id == Company.id)
            base_query = base_query.filter(Company.industry.ilike(f"%{industry}%"))

        overall_query = base_query

        overall_stats = SalaryAnalyticsService._calculate_statistics(db, overall_query)

        experience_breakdown = {}
        for level in ExperienceLevel:
            level_query = base_query.filter(Salary.experience_level == level)
            level_stats = SalaryAnalyticsService._calculate_statistics(db, level_query)
            if level_stats["count"] > 0:
                experience_breakdown[level.value] = level_stats

        employment_breakdown = {}
        for emp_type in EmploymentType:
            type_query = base_query.filter(Salary.employment_type == emp_type)
            type_stats = SalaryAnalyticsService._calculate_statistics(db, type_query)
            if type_stats["count"] > 0:
                employment_breakdown[emp_type.value] = type_stats

        location_breakdown = {}
        locations_query = db.query(
            Salary.location,
            func.count(Salary.id).label("count"),
            func.avg(Salary.salary_amount).label("avg"),
            func.min(Salary.salary_amount).label("min"),
            func.max(Salary.salary_amount).label("max")
        ).filter(
            Salary.location.isnot(None)
        ).group_by(
            Salary.location
        ).order_by(
            func.count(Salary.id).desc()
        ).limit(5)

        for loc in locations_query:
            if loc.count > 0:
                location_breakdown[loc.location] = {
                    "avg_salary": float(loc.avg),
                    "min_salary": float(loc.min),
                    "max_salary": float(loc.max),
                    "count": loc.count
                }

        industry_breakdown = {}
        industry_query = db.query(
            Company.industry,
            func.count(Salary.id).label("count"),
            func.avg(Salary.salary_amount).label("avg"),
            func.min(Salary.salary_amount).label("min"),
            func.max(Salary.salary_amount).label("max")
        ).join(
            Company, Salary.company_id == Company.id
        ).filter(
            Company.industry.isnot(None)
        ).group_by(
            Company.industry
        ).order_by(
            func.count(Salary.id).desc()
        ).limit(5)

        for ind in industry_query:
            if ind.count > 0:
                industry_breakdown[ind.industry] = {
                    "avg_salary": float(ind.avg),
                    "min_salary": float(ind.min),
                    "max_salary": float(ind.max),
                    "count": ind.count
                }

        return {
            "overall": overall_stats,
            "experience_level_breakdown": experience_breakdown,
            "employment_type_breakdown": employment_breakdown,
            "location_breakdown": location_breakdown,
            "industry_breakdown": industry_breakdown,
            "currency": currency,
            "filters": {
                "job_title": job_title,
                "company_id": company_id,
                "industry": industry,
                "location": location
            }
        }

    @staticmethod
    def get_comparative_analysis(
            db: Session,
            job_title: str,
            company_id: Optional[int] = None,
            location: Optional[str] = None,
            experience_level: Optional[ExperienceLevel] = None,
            employment_type: Optional[EmploymentType] = None,
            currency: str = "USD"
    ) -> Dict[str, Any]:
        result = {
            "job_title": job_title,
            "currency": currency,
            "company_comparison": None,
            "location_comparison": None,
            "filters": {
                "company_id": company_id,
                "location": location,
                "experience_level": experience_level.value if experience_level else None,
                "employment_type": employment_type.value if employment_type else None
            }
        }

        base_query = db.query(Salary).filter(
            Salary.job_title.ilike(f"%{job_title}%"),
            Salary.currency == currency
        )

        if experience_level:
            base_query = base_query.filter(Salary.experience_level == experience_level)

        if employment_type:
            base_query = base_query.filter(Salary.employment_type == employment_type)

        if company_id:
            company = db.query(Company).filter(Company.id == company_id).first()

            if company:
                company_query = base_query.filter(Salary.company_id == company_id)
                company_stats = SalaryAnalyticsService._calculate_statistics(db, company_query)

                industry_query = base_query.join(
                    Company, Salary.company_id == Company.id
                ).filter(
                    Company.industry == company.industry,
                    Salary.company_id != company_id
                )
                industry_stats = SalaryAnalyticsService._calculate_statistics(db, industry_query)

                if company_stats["count"] > 0 and industry_stats["count"] > 0:
                    # Calculate percentage difference
                    percent_diff = ((company_stats["avg_salary"] - industry_stats["avg_salary"]) /
                                    industry_stats["avg_salary"]) * 100

                    result["company_comparison"] = {
                        "company_name": company.name,
                        "company_avg_salary": company_stats["avg_salary"],
                        "company_sample_size": company_stats["count"],
                        "industry_name": company.industry,
                        "industry_avg_salary": industry_stats["avg_salary"],
                        "industry_sample_size": industry_stats["count"],
                        "percent_difference": round(percent_diff, 2),
                        "is_above_industry_avg": percent_diff > 0
                    }

        if location:
            location_query = base_query.filter(Salary.location.ilike(f"%{location}%"))
            location_stats = SalaryAnalyticsService._calculate_statistics(db, location_query)

            national_query = base_query.filter(
                ~Salary.location.ilike(f"%{location}%")
            )
            national_stats = SalaryAnalyticsService._calculate_statistics(db, national_query)

            if location_stats["count"] > 0 and national_stats["count"] > 0:
                percent_diff = ((location_stats["avg_salary"] - national_stats["avg_salary"]) /
                                national_stats["avg_salary"]) * 100

                result["location_comparison"] = {
                    "location_name": location,
                    "location_avg_salary": location_stats["avg_salary"],
                    "location_sample_size": location_stats["count"],
                    "national_avg_salary": national_stats["avg_salary"],
                    "national_sample_size": national_stats["count"],
                    "percent_difference": round(percent_diff, 2),
                    "is_above_national_avg": percent_diff > 0
                }

        return result

    @staticmethod
    def _calculate_statistics(db: Session, query) -> Dict[str, Any]:
        stats = db.query(
            func.count(Salary.id).label("count"),
            func.avg(Salary.salary_amount).label("avg"),
            func.min(Salary.salary_amount).label("min"),
            func.max(Salary.salary_amount).label("max"),
            func.stddev(Salary.salary_amount).label("stddev")
        ).select_from(query.subquery()).first()

        result = {
            "count": stats.count,
            "avg_salary": float(stats.avg) if stats.avg is not None else 0,
            "min_salary": float(stats.min) if stats.min is not None else 0,
            "max_salary": float(stats.max) if stats.max is not None else 0,
            "stddev": float(stats.stddev) if stats.stddev is not None else 0
        }

        if stats.count == 0:
            return result

        salaries = [float(s.salary_amount) for s in query.all()]

        if salaries:
            try:
                result["median"] = statistics.median(salaries)
                result["percentile_25"] = statistics.quantiles(salaries, n=4)[0]
                result["percentile_75"] = statistics.quantiles(salaries, n=4)[2]

                if len(salaries) >= 10:
                    result["percentile_10"] = statistics.quantiles(salaries, n=10)[0]
                    result["percentile_90"] = statistics.quantiles(salaries, n=10)[8]
            except Exception as e:
                logger.error(f"Error calculating percentiles: {e}")

        return result