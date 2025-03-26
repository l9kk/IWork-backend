from sqlalchemy.orm import Session

from app.models.review import Review, ReviewStatus


def test_review_model(db: Session, test_review: Review):
    """Test review model retrieval"""
    db_review = db.query(Review).filter(Review.id == test_review.id).first()

    assert db_review is not None
    assert db_review.rating == 4.5
    assert db_review.employee_status == "FORMER"
    assert "Great team" in db_review.pros
    assert "Limited growth" in db_review.cons
    assert db_review.status == ReviewStatus.VERIFIED
    assert db_review.is_anonymous is False