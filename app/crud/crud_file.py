from typing import Optional, Dict, Any, Type

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.file import FileAttachment
from app.schemas.file import FileAttachmentCreate, FileAttachmentUpdate
from app.services.s3 import delete_file_from_s3


class CRUDFileAttachment(
    CRUDBase[FileAttachment, FileAttachmentCreate, FileAttachmentUpdate]
):
    def create_from_s3_data(
        self, db: Session, *, s3_data: Dict[str, Any]
    ) -> FileAttachment:
        db_obj = FileAttachment(**s3_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_user_files(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> list[Type[FileAttachment]]:
        return (
            db.query(FileAttachment)
            .filter(FileAttachment.user_id == user_id)
            .order_by(FileAttachment.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_review_files(
        self, db: Session, *, review_id: int, skip: int = 0, limit: int = 100
    ) -> list[Type[FileAttachment]]:
        return (
            db.query(FileAttachment)
            .filter(FileAttachment.review_id == review_id)
            .order_by(FileAttachment.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def delete_with_s3(self, db: Session, *, id: int) -> Optional[FileAttachment]:
        file = self.get(db, id=id)
        if not file:
            return None

        delete_file_from_s3(file.s3_key, file.s3_bucket)

        db.delete(file)
        db.commit()
        return file


file_attachment = CRUDFileAttachment(FileAttachment)
