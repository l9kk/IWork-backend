from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.base import get_db
from app import crud
from app.models.review import ReviewStatus
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewUpdate, ReviewResponse, AdminReviewResponse
from app.core.dependencies import get_current_user, get_current_admin_user
from app.utils.redis_cache import RedisClient, get_redis
from app.services.ai_scanner import scan_review_content
from app.core.config import settings

router = APIRouter()


@router.post("/", response_model=ReviewResponse)
async def create_review(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        review_in: ReviewCreate,
        current_user: User = Depends(get_current_user)
):
    """
    Create a new company review
    """
    # Check if company exists
    company = crud.company.get(db, id=review_in.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    review = crud.review.create_with_owner(db, obj_in=review_in, user_id=current_user.id)

    # Run AI scanner on the review content
    if settings.AI_SCANNER_ENABLED:
        content_to_scan = f"{review.pros or ''} {review.cons or ''} {review.recommendations or ''}"
        scan_results = await scan_review_content(content_to_scan)

        for flag_type, flagged_items in scan_results.items():
            for item in flagged_items:
                crud.review.add_ai_flag(
                    db,
                    review_id=review.id,
                    flag_type=flag_type,
                    flag_description=f"Potentially {flag_type} content detected",
                    flagged_text=item
                )

    # Invalidate cache
    await redis.delete(f"company:detail:{review.company_id}")
    await redis.delete_pattern(f"company:reviews:{review.company_id}*")

    # Return response
    user_name = None
    if not review.is_anonymous:
        user_name = f"{current_user.first_name} {current_user.last_name}".strip()
        if not user_name:
            user_name = "User"

    return ReviewResponse(
        id=review.id,
        company_id=review.company_id,
        company_name=company.name,
        rating=review.rating,
        employee_status=review.employee_status,
        employment_start_date=review.employment_start_date,
        employment_end_date=review.employment_end_date,
        pros=review.pros,
        cons=review.cons,
        recommendations=review.recommendations,
        status=review.status,
        created_at=review.created_at,
        user_name=user_name
    )


@router.get("/company/{company_id}", response_model=List[ReviewResponse])
async def get_company_reviews(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        company_id: int,
        skip: int = 0,
        limit: int = 20
):
    """
    Get reviews for a specific company
    """
    # Check if company exists
    company = crud.company.get(db, id=company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    cache_key = f"company:reviews:{company_id}:{skip}:{limit}"
    cached_result = await redis.get(cache_key)
    if cached_result:
        return cached_result

    # Only show verified reviews to regular users
    reviews = crud.review.get_company_reviews(
        db, company_id=company_id, skip=skip, limit=limit
    )

    result = []
    for review in reviews:
        user_name = None
        if not review.is_anonymous:
            user = crud.user.get(db, id=review.user_id)
            if user:
                user_name = f"{user.first_name} {user.last_name}".strip()
                if not user_name:
                    user_name = "User"

        result.append(ReviewResponse(
            id=review.id,
            company_id=review.company_id,
            company_name=company.name,
            rating=review.rating,
            employee_status=review.employee_status,
            employment_start_date=review.employment_start_date,
            employment_end_date=review.employment_end_date,
            pros=review.pros,
            cons=review.cons,
            recommendations=review.recommendations,
            status=review.status,
            created_at=review.created_at,
            user_name=user_name
        ))

    # Cache reviews for 1 hour
    await redis.set(cache_key, result, expire=3600)

    return result


@router.get("/user/me", response_model=List[ReviewResponse])
async def get_my_reviews(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        skip: int = 0,
        limit: int = 50
):
    """
    Get the current user's reviews
    """
    reviews = crud.review.get_user_reviews(
        db, user_id=current_user.id, skip=skip, limit=limit
    )

    result = []
    for review in reviews:
        company = crud.company.get(db, id=review.company_id)
        company_name = company.name if company else "Unknown Company"

        result.append(ReviewResponse(
            id=review.id,
            company_id=review.company_id,
            company_name=company_name,
            rating=review.rating,
            employee_status=review.employee_status,
            employment_start_date=review.employment_start_date,
            employment_end_date=review.employment_end_date,
            pros=review.pros,
            cons=review.cons,
            recommendations=review.recommendations,
            status=review.status,
            created_at=review.created_at,
            user_name=f"{current_user.first_name} {current_user.last_name}".strip() or "User"
        ))

    return result


@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
        *,
        db: Session = Depends(get_db),
        redis: RedisClient = Depends(get_redis),
        review_id: int,
        review_in: ReviewUpdate,
        current_user: User = Depends(get_current_user)
):
    """
    Update a user's review
    """
    review = crud.review.get(db, id=review_id)
    if not review or review.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Review not found or not owned by user")

    # Don't allow updates for verified reviews to prevent edit after approval
    if review.status == ReviewStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a verified review. Please create a new review instead."
        )

    updated_review = crud.review.update(db, db_obj=review, obj_in=review_in)

    # Reset status to pending if content is modified
    content_fields = ["pros", "cons", "recommendations", "rating"]
    update_data = review_in.dict(exclude_unset=True)

    if any(field in update_data for field in content_fields):
        updated_review = crud.review.update_status(
            db, review_id=review_id, status=ReviewStatus.PENDING
        )

        # Re-run AI scanner
        if settings.AI_SCANNER_ENABLED:
            # First delete old flags
            crud.review.clear_ai_flags(db, review_id=review_id)

            # Run new scan
            content_to_scan = f"{review.pros or ''} {review.cons or ''} {review.recommendations or ''}"
            scan_results = await scan_review_content(content_to_scan)

            for flag_type, flagged_items in scan_results.items():
                for item in flagged_items:
                    crud.review.add_ai_flag(
                        db,
                        review_id=review.id,
                        flag_type=flag_type,
                        flag_description=f"Potentially {flag_type} content detected",
                        flagged_text=item
                    )

    # Invalidate cache
    await redis.delete(f"company:detail:{review.company_id}")
    await redis.delete_pattern(f"company:reviews:{review.company_id}*")

    # Get company name
    company = crud.company.get(db, id=review.company_id)
    company_name = company.name if company else "Unknown Company"

    return ReviewResponse(
        id=updated_review.id,
        company_id=updated_review.company_id,
        company_name=company_name,
        rating=updated_review.rating,
        employee_status=updated_review.employee_status,
        employment_start_date=updated_review.employment_start_date,
        employment_end_date=updated_review.employment_end_date,
        pros=updated_review.pros,
        cons=updated_review.cons,
        recommendations=updated_review.recommendations,
        status=updated_review.status,
        created_at=updated_review.created_at,
        user_name=f"{current_user.first_name} {current_user.last_name}".strip() or "User"
    )