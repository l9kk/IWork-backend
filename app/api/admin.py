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
from app.schemas.review import AdminReviewResponse
from app.services.email import send_review_approved_email, send_review_rejected_email, get_email_db_session
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
            "user_email": user.email if user else "Unknown",
            "has_ai_flags": bool(review.ai_scanner_flags)
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

        # Get AI scanner flags if any
        ai_flags = []
        for flag in review.ai_scanner_flags:
            ai_flags.append({
                "flag_type": flag.flag_type,
                "flag_description": flag.flag_description,
                "flagged_text": flag.flagged_text
            })

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
            moderation_notes=review.moderation_notes,
            ai_scanner_flags=ai_flags
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

    # Get AI scanner flags
    ai_flags = []
    for flag in review.ai_scanner_flags:
        ai_flags.append({
            "flag_type": flag.flag_type,
            "flag_description": flag.flag_description,
            "flagged_text": flag.flagged_text
        })

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
        moderation_notes=review.moderation_notes,
        ai_scanner_flags=ai_flags
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

    # Get AI scanner flags
    ai_flags = []
    for flag in review.ai_scanner_flags:
        ai_flags.append({
            "flag_type": flag.flag_type,
            "flag_description": flag.flag_description,
            "flagged_text": flag.flagged_text
        })

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
        moderation_notes=review.moderation_notes,
        ai_scanner_flags=ai_flags
    )