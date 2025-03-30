from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import crud
from app.core.config import settings
from app.core.dependencies import get_current_admin_user
from app.db.base import get_db
from app.models.review import ReviewStatus, Review
from app.models.user import User
from app.models.company import Company
from app.models.salary import Salary, ExperienceLevel, EmploymentType
from app.schemas.review import AdminReviewResponse
from app.services.email import send_review_approved_email, send_review_rejected_email, get_email_db_session
from app.services.ai_scanner import scan_review_content
from app.utils.redis_cache import RedisClient, get_redis

router = APIRouter()


@router.get("/dashboard", response_model=Dict[str, Any])
async def admin_dashboard(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        current_admin: User = Depends(get_current_admin_user)
):
    cache_key = "admin:dashboard"
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    # Get reviews pending moderation
    pending_reviews = crud.review.get_pending_reviews(db, limit=5)

    # Count of pending reviews
    pending_reviews_count = len(pending_reviews)

    # Today's date for new reviews today
    today = datetime.now().date()

    # Build dashboard data
    latest_reviews_data = []
    for review in pending_reviews:
        company = crud.company.get(db, id=review.company_id)
        user = crud.user.get(db, id=review.user_id)

        latest_reviews_data.append({
            "id": review.id,
            "company_name": company.name if company else "Unknown",
            "rating": review.rating,
            "created_at": review.created_at,
            "user_email": user.email if user else "Unknown"
        })

    # Get counts
    new_reviews_today = db.query(func.count(Review.id)).filter(
        func.date(Review.created_at) == today
    ).scalar()

    total_reviews = db.query(func.count(Review.id)).scalar()
    total_companies = db.query(func.count(Company.id)).scalar()
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(
        User.is_active == True
    ).scalar()

    result = {
        "reviews": {
            "pending": pending_reviews_count,
            "new_today": new_reviews_today,
            "total": total_reviews
        },
        "companies": {
            "total": total_companies
        },
        "users": {
            "total": total_users,
            "active": active_users
        },
        "latest_pending_reviews": latest_reviews_data
    }

    # Cache for 10 minutes
    await redis.set(cache_key, result, expire=600)

    return result


@router.get("/reviews/pending", response_model=List[AdminReviewResponse])
async def admin_pending_reviews(
        *,
        db: Session = Depends(get_db),
        current_admin: User = Depends(get_current_admin_user),
        skip: int = 0,
        limit: int = 20
):
    reviews = crud.review.get_pending_reviews(db, skip=skip, limit=limit)

    result = []
    for review in reviews:
        company = crud.company.get(db, id=review.company_id)
        user = crud.user.get(db, id=review.user_id)

        result.append(AdminReviewResponse(
            id=review.id,
            company_id=review.company_id,
            company_name=company.name if company else "Unknown Company",
            rating=review.rating,
            employee_status=review.employee_status,
            employment_start_date=review.employment_start_date,
            employment_end_date=review.employment_end_date,
            pros=review.pros,
            cons=review.cons,
            recommendations=review.recommendations,
            status=review.status,
            created_at=review.created_at,
            user_id=review.user_id,
            user_name=f"{user.first_name} {user.last_name}" if user else "Unknown User",
            moderation_notes=review.moderation_notes
        ))

    return result


@router.put("/reviews/{review_id}/approve", response_model=AdminReviewResponse)
async def admin_approve_review(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        review_id: int,
        moderation_notes: Optional[str] = None,
        current_admin: User = Depends(get_current_admin_user)
):
    review = crud.review.get(db, id=review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.status != ReviewStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending reviews can be approved")

    # Get user and company for email notification
    user = crud.user.get(db, id=review.user_id)
    company = crud.company.get(db, id=review.company_id)

    review = crud.review.update_status(
        db,
        review_id=review_id,
        status=ReviewStatus.VERIFIED,
        moderation_notes=moderation_notes
    )

    # Invalidate caches
    await redis.delete(f"company:detail:{review.company_id}")
    await redis.delete_pattern(f"company:reviews:{review.company_id}*")
    await redis.delete("admin:dashboard")

    # Send notification email if enabled for the user
    if user and settings.EMAILS_ENABLED:
        with get_email_db_session() as email_db:
            user_settings = crud.account_settings.get_by_user_id(email_db, user_id=user.id)
            if user_settings and user_settings.email_notifications_enabled and user_settings.notify_on_review_approval:
                await send_review_approved_email(
                    user_email=user.email,
                    user_first_name=user.first_name or "User",
                    company_name=company.name if company else "a company",
                    review_id=review.id
                )

    return AdminReviewResponse(
        id=review.id,
        company_id=review.company_id,
        company_name=company.name if company else "Unknown Company",
        rating=review.rating,
        employee_status=review.employee_status,
        employment_start_date=review.employment_start_date,
        employment_end_date=review.employment_end_date,
        pros=review.pros,
        cons=review.cons,
        recommendations=review.recommendations,
        status=review.status,
        created_at=review.created_at,
        user_id=review.user_id,
        user_name=f"{user.first_name} {user.last_name}" if user else "Unknown User",
        moderation_notes=review.moderation_notes
    )


@router.put("/reviews/{review_id}/reject", response_model=AdminReviewResponse)
async def admin_reject_review(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        review_id: int,
        moderation_notes: str,
        current_admin: User = Depends(get_current_admin_user)
):
    review = crud.review.get(db, id=review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.status != ReviewStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending reviews can be rejected")

    # Get user and company for email notification
    user = crud.user.get(db, id=review.user_id)
    company = crud.company.get(db, id=review.company_id)

    review = crud.review.update_status(
        db,
        review_id=review_id,
        status=ReviewStatus.REJECTED,
        moderation_notes=moderation_notes
    )

    # Invalidate cache
    await redis.delete("admin:dashboard")

    # Send notification email if enabled for the user
    if user and settings.EMAILS_ENABLED:
        with get_email_db_session() as email_db:
            user_settings = crud.account_settings.get_by_user_id(email_db, user_id=user.id)
            if user_settings and user_settings.email_notifications_enabled and user_settings.notify_on_review_rejection:
                await send_review_rejected_email(
                    user_email=user.email,
                    user_first_name=user.first_name or "User",
                    company_name=company.name if company else "a company",
                    rejection_reason=moderation_notes
                )

    return AdminReviewResponse(
        id=review.id,
        company_id=review.company_id,
        company_name=company.name if company else "Unknown Company",
        rating=review.rating,
        employee_status=review.employee_status,
        employment_start_date=review.employment_start_date,
        employment_end_date=review.employment_end_date,
        pros=review.pros,
        cons=review.cons,
        recommendations=review.recommendations,
        status=review.status,
        created_at=review.created_at,
        user_id=review.user_id,
        user_name=f"{user.first_name} {user.last_name}" if user else "Unknown User",
        moderation_notes=review.moderation_notes
    )


@router.get("/salaries", response_model=Dict[str, Any])
async def admin_get_salaries(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        current_admin: User = Depends(get_current_admin_user),
        job_title: Optional[str] = None,
        company_id: Optional[int] = None,
        user_id: Optional[int] = None,
        experience_level: Optional[ExperienceLevel] = None,
        employment_type: Optional[EmploymentType] = None,
        location: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
):
    cache_key = f"admin:salaries:{hash((job_title, company_id, user_id, experience_level, employment_type, location, skip, limit))}"
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result
    
    query = db.query(Salary)
    
    if job_title:
        query = query.filter(Salary.job_title.ilike(f"%{job_title}%"))
    
    if company_id:
        query = query.filter(Salary.company_id == company_id)
    
    if user_id:
        query = query.filter(Salary.user_id == user_id)
    
    if experience_level:
        query = query.filter(Salary.experience_level == experience_level)
    
    if employment_type:
        query = query.filter(Salary.employment_type == employment_type)
    
    if location:
        query = query.filter(Salary.location.ilike(f"%{location}%"))
    
    total_count = query.count()
    
    salaries = query.order_by(Salary.created_at.desc()).offset(skip).limit(limit).all()
    
    results = []
    for salary in salaries:
        company = crud.company.get(db, id=salary.company_id)
        user = crud.user.get(db, id=salary.user_id)
        
        results.append({
            "id": salary.id,
            "user_id": salary.user_id,
            "user_email": user.email if user else "Unknown",
            "company_id": salary.company_id,
            "company_name": company.name if company else "Unknown Company",
            "job_title": salary.job_title,
            "salary_amount": salary.salary_amount,
            "currency": salary.currency,
            "experience_level": salary.experience_level,
            "employment_type": salary.employment_type,
            "location": salary.location,
            "is_anonymous": salary.is_anonymous,
            "created_at": salary.created_at.isoformat()
        })
    
    response = {
        "results": results,
        "total": total_count,
        "filters_applied": {
            "job_title": job_title,
            "company_id": company_id,
            "user_id": user_id,
            "experience_level": experience_level.value if experience_level else None,
            "employment_type": employment_type.value if employment_type else None,
            "location": location
        },
        "skip": skip,
        "limit": limit
    }
    
    # Cache for 5 minutes
    await redis.set(cache_key, response, expire=300)
    
    return response


@router.get("/salaries/duplicates", response_model=Dict[str, Any])
async def admin_find_duplicate_salaries(
        *,
        db: Session = Depends(get_db),
        current_admin: User = Depends(get_current_admin_user),
        time_window_days: int = 30
):
    duplicates = crud.salary.find_potential_duplicates(db, time_window_days=time_window_days)
    
    result_groups = []
    for duplicate_group in duplicates:
        group_entries = []
        for salary in duplicate_group:
            company = crud.company.get(db, id=salary.company_id)
            user = crud.user.get(db, id=salary.user_id)
            
            group_entries.append({
                "id": salary.id,
                "user_id": salary.user_id,
                "user_email": user.email if user else "Unknown",
                "company_id": salary.company_id,
                "company_name": company.name if company else "Unknown Company",
                "job_title": salary.job_title,
                "salary_amount": salary.salary_amount,
                "currency": salary.currency,
                "experience_level": salary.experience_level,
                "employment_type": salary.employment_type,
                "created_at": salary.created_at.isoformat()
            })
        
        if len(group_entries) > 1:
            result_groups.append(group_entries)
    
    return {
        "duplicate_groups": result_groups,
        "total_groups": len(result_groups),
        "time_window_days": time_window_days
    }


@router.delete("/salaries/{salary_id}", response_model=Dict[str, Any])
async def admin_delete_salary(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        salary_id: int,
        current_admin: User = Depends(get_current_admin_user)
):
    salary = crud.salary.get(db, id=salary_id)
    if not salary:
        raise HTTPException(status_code=404, detail="Salary entry not found")
    
    company_id = salary.company_id
    job_title = salary.job_title
    
    crud.salary.remove(db, id=salary_id)
    
    # Invalidate caches
    await redis.delete_pattern(f"admin:salaries*")
    await redis.delete_pattern(f"company:salaries:{company_id}*")
    await redis.delete_pattern(f"salary:statistics:{job_title}*")
    
    return {
        "status": "success",
        "message": f"Salary entry {salary_id} has been deleted",
        "deleted_salary_id": salary_id
    }


@router.get("/ai-scanner", response_model=Dict[str, Any])
async def scan_review_with_ai(
        *,
        current_admin: User = Depends(get_current_admin_user),
        review_id: int,
        db: Session = Depends(get_db)
):
    """
    Scan a review for potentially inappropriate content using AI and store the results.
    
    Uses the enhanced Gemini AI scanner to scan a review's content and stores any flags in the database.
    Returns whether the content is safe ("yes") or potentially harmful ("no").
    """
    review = crud.review.get(db, id=review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    if not settings.AI_SCANNER_ENABLED:
        raise HTTPException(status_code=400, detail="AI Scanner is disabled")
    
    # Combine all text fields for scanning
    content_to_scan = f"{review.pros or ''} {review.cons or ''} {review.recommendations or ''}"
    scan_results = await scan_review_content(content_to_scan)
    
    # Extract the safety verdict
    is_safe = scan_results.pop("is_safe", False)
    safety_verdict = "yes" if is_safe else "no"
    
    # Clear existing flags
    crud.review.clear_ai_flags(db, review_id=review_id)
    
    # Add new flags
    flag_count = 0
    for flag_type, flagged_items in scan_results.items():
        for item in flagged_items:
            crud.review.add_ai_flag(
                db,
                review_id=review_id,
                flag_type=flag_type,
                flag_description=f"Potentially {flag_type} content detected",
                flagged_text=item
            )
            flag_count += 1
    
    return {
        "review_id": review_id,
        "is_safe": safety_verdict,  # "yes" or "no"
        "has_flags": flag_count > 0,
        "flags_count": flag_count,
        "scan_results": scan_results,
        "message": f"Review #{review_id} scanned successfully. Found {flag_count} potential issues."
    }