from typing import Optional
from pydantic import BaseModel, HttpUrl
from datetime import datetime

from app.models.file import FileType


class FileAttachmentBase(BaseModel):
    file_type: FileType
    description: Optional[str] = None


class FileAttachmentCreate(FileAttachmentBase):
    pass


class FileAttachmentUpdate(BaseModel):
    description: Optional[str] = None


class FileAttachmentResponse(FileAttachmentBase):
    id: int
    filename: str
    original_filename: str
    file_size: int
    content_type: str
    file_url: HttpUrl
    user_id: int
    review_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    file: FileAttachmentResponse
    message: str