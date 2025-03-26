from sqlalchemy.orm import Session

from app import crud
from app.models.review import ReviewStatus, EmployeeStatus
from app.schemas.review import ReviewCreate


def test_create_review_with_owner(db: Session, test_user, test_company):
    """Test creating a new review with owner"""
    review_in = ReviewCreate(
        company_id=test_company.id,
        rating=3.5,
        employee_status=EmployeeStatus.CURRENT,
        pros="Good work environment",
        cons="Low salary",
        recommendations="Improve compensation",
        is_anonymous=True
    )

    review = crud.review.create_with_owner(db, obj_in=review_in, user_id=test_user.id)

    assert review.company_id == test_company.id
    assert review.user_id == test_user.id
    assert review.rating == 3.5
    assert review.employee_status == EmployeeStatus.CURRENT
    assert review.pros == "Good work environment"
    assert review.status == ReviewStatus.PENDING
    assert review.is_anonymous is True


def test_get_company_reviews(db: Session, test_review, test_company):
    """Test getting all reviews for a company"""
    review_in = ReviewCreate(
        company_id=test_company.id,
        rating=4.0,
        employee_status=EmployeeStatus.CURRENT,
        pros="Another review",
        is_anonymous=True
    )

    other_review = crud.review.create_with_owner(
        db, obj_in=review_in, user_id=test_review.user_id
    )

    crud.review.update_status(
        db, review_id=other_review.id, status=ReviewStatus.VERIFIED
    )

    company_reviews = crud.review.get_company_reviews(db, company_id=test_company.id)

    assert len(company_reviews) == 2
    assert all(review.company_id == test_company.id for review in company_reviews)
    assert all(review.status == ReviewStatus.VERIFIED for review in company_reviews)


def test_get_user_reviews(db: Session, test_review, test_user):
    """Test getting all reviews by a user"""
    user_reviews = crud.review.get_user_reviews(db, user_id=test_user.id)

    assert len(user_reviews) >= 1
    assert any(review.id == test_review.id for review in user_reviews)
    assert all(review.user_id == test_user.id for review in user_reviews)


def test_update_review_status(db: Session, test_review):
    """Test updating a review's status"""
    updated_review = crud.review.update_status(
        db,
        review_id=test_review.id,
        status=ReviewStatus.REJECTED,
        moderation_notes="Contains inappropriate content"
    )

    assert updated_review.status == ReviewStatus.REJECTED
    assert updated_review.moderation_notes == "Contains inappropriate content"