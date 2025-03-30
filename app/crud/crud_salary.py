from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.salary import Salary, ExperienceLevel, EmploymentType
from app.schemas.salary import SalaryCreate, SalaryUpdate


class CRUDSalary(CRUDBase[Salary, SalaryCreate, SalaryUpdate]):
    def _normalize_enum_value(self, value, enum_class):
        if hasattr(value, 'value'):
            return value.value
        elif isinstance(value, str):
            try:
                return enum_class(value).value
            except ValueError:
                try:
                    return getattr(enum_class, value).value
                except (AttributeError, TypeError):
                    return None
        return None
        
    def create_with_owner(
            self, db: Session, *, obj_in: SalaryCreate, user_id: int
    ) -> Salary:
        obj_in_data = obj_in.dict()
        
        if 'experience_level' in obj_in_data:
            normalized = self._normalize_enum_value(obj_in_data['experience_level'], ExperienceLevel)
            if normalized:
                obj_in_data['experience_level'] = normalized
        
        if 'employment_type' in obj_in_data:
            normalized = self._normalize_enum_value(obj_in_data['employment_type'], EmploymentType)
            if normalized:
                obj_in_data['employment_type'] = normalized
        
        db_obj = Salary(**obj_in_data, user_id=user_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, *, db_obj: Salary, obj_in: SalaryUpdate
    ) -> Salary:
        obj_data = obj_in.dict(exclude_unset=True)
        
        if 'experience_level' in obj_data:
            normalized = self._normalize_enum_value(obj_data['experience_level'], ExperienceLevel)
            if normalized:
                obj_data['experience_level'] = normalized
                        
        if 'employment_type' in obj_data:
            normalized = self._normalize_enum_value(obj_data['employment_type'], EmploymentType)
            if normalized:
                obj_data['employment_type'] = normalized
        
        return super().update(db, db_obj=db_obj, obj_in=obj_data)

    def get_company_salaries(
            self,
            db: Session,
            *,
            company_id: int,
            job_title: Optional[str] = None,
            experience_level: Optional[ExperienceLevel] = None,
            employment_type: Optional[EmploymentType] = None,
            skip: int = 0,
            limit: int = 100
    ) -> List[Salary]:
        query = db.query(Salary).filter(Salary.company_id == company_id)

        if job_title:
            query = query.filter(Salary.job_title.ilike(f"%{job_title}%"))

        if experience_level:
            query = query.filter(Salary.experience_level == experience_level)

        if employment_type:
            query = query.filter(Salary.employment_type == employment_type)

        return query.order_by(Salary.created_at.desc()).offset(skip).limit(limit).all()

    def get_user_salaries(
            self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[Salary]:
        return db.query(Salary).filter(
            Salary.user_id == user_id
        ).order_by(Salary.created_at.desc()).offset(skip).limit(limit).all()

    def search_salaries(
            self,
            db: Session,
            *,
            job_title: Optional[str] = None,
            company_id: Optional[int] = None,
            location: Optional[str] = None,
            experience_level: Optional[ExperienceLevel] = None,
            employment_type: Optional[EmploymentType] = None,
            min_salary: Optional[float] = None,
            max_salary: Optional[float] = None,
            skip: int = 0,
            limit: int = 100
    ) -> List[Salary]:
        query = db.query(Salary)

        if job_title:
            query = query.filter(Salary.job_title.ilike(f"%{job_title}%"))

        if company_id:
            query = query.filter(Salary.company_id == company_id)

        if location:
            query = query.filter(Salary.location.ilike(f"%{location}%"))

        if experience_level:
            query = query.filter(Salary.experience_level == experience_level)

        if employment_type:
            query = query.filter(Salary.employment_type == employment_type)

        if min_salary is not None:
            query = query.filter(Salary.salary_amount >= min_salary)

        if max_salary is not None:
            query = query.filter(Salary.salary_amount <= max_salary)

        return query.order_by(Salary.created_at.desc()).offset(skip).limit(limit).all()

    def get_salary_statistics(
            self,
            db: Session,
            *,
            job_title: str,
            experience_level: Optional[ExperienceLevel] = None,
            location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = db.query(
            Salary.job_title,
            Salary.currency,
            func.avg(Salary.salary_amount).label("avg_salary"),
            func.min(Salary.salary_amount).label("min_salary"),
            func.max(Salary.salary_amount).label("max_salary"),
            func.count(Salary.id).label("sample_size")
        ).filter(Salary.job_title.ilike(f"%{job_title}%"))

        if experience_level:
            query = query.filter(Salary.experience_level == experience_level)

        if location:
            query = query.filter(Salary.location.ilike(f"%{location}%"))

        query = query.group_by(Salary.job_title, Salary.currency)

        result = []
        for row in query.all():
            result.append({
                "job_title": row.job_title,
                "currency": row.currency,
                "avg_salary": float(row.avg_salary),
                "min_salary": float(row.min_salary),
                "max_salary": float(row.max_salary),
                "sample_size": row.sample_size
            })

        return result


salary = CRUDSalary(Salary)