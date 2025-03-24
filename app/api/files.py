from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.base import get_db
from app import crud
from app.models.user import User
from app.schemas.file import FileAttachmentResponse, FileUploadResponse
from app.core.dependencies import get_current_user
from app.services.s3 import upload_file_to_s3

router = APIRouter()
@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
        *,
        db: Session = Depends(get_db),
        file: UploadFile = File(...),
        description: Optional[str] = Form(None),
        review_id: Optional[int] = Form(None),
        current_user: User = Depends(get_current_user)
):
    if review_id:
        review = crud.review.get(db, id=review_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found"
            )
        if review.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to attach files to this review"
            )

    s3_data = await upload_file_to_s3(
        file=file,
        user_id=current_user.id,
        review_id=review_id,
        description=description
    )

    file_attachment = crud.file_attachment.create_from_s3_data(db, s3_data=s3_data)

    return FileUploadResponse(
        file=file_attachment,
        message="File uploaded successfully"
    )


@router.get("/my-files", response_model=List[FileAttachmentResponse])
def get_my_files(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        skip: int = 0,
        limit: int = 50
):
    files = crud.file_attachment.get_user_files(
        db, user_id=current_user.id, skip=skip, limit=limit
    )
    return files


@router.get("/review/{review_id}", response_model=List[FileAttachmentResponse])
def get_review_files(
        *,
        db: Session = Depends(get_db),
        review_id: int,
        skip: int = 0,
        limit: int = 20
):
    review = crud.review.get(db, id=review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    files = crud.file_attachment.get_review_files(
        db, review_id=review_id, skip=skip, limit=limit
    )
    return files


@router.get("/{file_id}", response_model=FileAttachmentResponse)
def get_file(
        *,
        db: Session = Depends(get_db),
        file_id: int
):
    file = crud.file_attachment.get(db, id=file_id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    return file


@router.delete("/{file_id}", response_model=dict)
def delete_file(
        *,
        db: Session = Depends(get_db),
        file_id: int,
        current_user: User = Depends(get_current_user)
):
    file = crud.file_attachment.get(db, id=file_id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    if file.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this file"
        )

    crud.file_attachment.delete_with_s3(db, id=file_id)

    return {"message": "File deleted successfully"}
