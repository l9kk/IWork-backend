from typing import Optional, Type
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.review import Review, AIScannerFlag, ReviewStatus
from app.schemas.review import ReviewCreate, ReviewUpdate


class CRUDReview(CRUDBase[Review, ReviewCreate, ReviewUpdate]):
    def create_with_owner(
            self, db: Session, *, obj_in: ReviewCreate, user_id: int
    ) -> Review:
        obj_in_data = obj_in.dict()
        db_obj = Review(**obj_in_data, user_id=user_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_company_reviews(
            self, db: Session, *, company_id: int, skip: int = 0, limit: int = 100
    ) -> list[Type[Review]]:
        return db.query(Review).filter(
            Review.company_id == company_id,
            Review.status == ReviewStatus.VERIFIED
        ).order_by(Review.created_at.desc()).offset(skip).limit(limit).all()

    def get_user_reviews(
            self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> list[Type[Review]]:
        return db.query(Review).filter(
            Review.user_id == user_id
        ).order_by(Review.created_at.desc()).offset(skip).limit(limit).all()

    def get_pending_reviews(
            self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> list[Type[Review]]:
        return db.query(Review).filter(
            Review.status == ReviewStatus.PENDING
        ).order_by(Review.created_at).offset(skip).limit(limit).all()

    def search_reviews(
            self,
            db: Session,
            *,
            query: Optional[str] = None,
            company_id: Optional[int] = None,
            min_rating: Optional[float] = None,
            max_rating: Optional[float] = None,
            skip: int = 0,
            limit: int = 100
    ) -> list[Type[Review]]:
        search_query = db.query(Review).filter(Review.status == ReviewStatus.VERIFIED)

        if query:
            search_query = search_query.filter(
                or_(
                    Review.pros.ilike(f"%{query}%"),
                    Review.cons.ilike(f"%{query}%"),
                    Review.recommendations.ilike(f"%{query}%")
                )
            )

        if company_id:
            search_query = search_query.filter(Review.company_id == company_id)

        if min_rating is not None:
            search_query = search_query.filter(Review.rating >= min_rating)

        if max_rating is not None:
            search_query = search_query.filter(Review.rating <= max_rating)

        return search_query.order_by(Review.created_at.desc()).offset(skip).limit(limit).all()

    def update_status(
            self, db: Session, *, review_id: int, status: ReviewStatus, moderation_notes: Optional[str] = None
    ) -> Type[Review] | None:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            return None

        review.status = status
        if moderation_notes:
            review.moderation_notes = moderation_notes

        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    def add_ai_flag(
            self, db: Session, *, review_id: int, flag_type: str, flag_description: str,
            flagged_text: Optional[str] = None
    ) -> AIScannerFlag:
        flag = AIScannerFlag(
            review_id=review_id,
            flag_type=flag_type,
            flag_description=flag_description,
            flagged_text=flagged_text
        )
        db.add(flag)
        db.commit()
        db.refresh(flag)
        return flag

    def clear_ai_flags(self, db: Session, *, review_id: int) -> None:
        db.query(AIScannerFlag).filter(AIScannerFlag.review_id == review_id).delete()
        db.commit()

    def get_with_attachments(self, db: Session, *, id: int) -> Optional[Review]:
        return db.query(Review).filter(Review.id == id).options(
            joinedload(Review.file_attachments)
        ).first()


review = CRUDReview(Review)