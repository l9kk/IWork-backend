import uuid
import logging
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException, status

from app.core.config import settings
from app.models.file import FileType

logger = logging.getLogger(__name__)


def get_s3_client():
    """
    Create and return an S3 client instance
    """
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )


def determine_file_type(content_type: str) -> FileType:
    """
    Determine the file type based on content type
    """
    if content_type.startswith('image/'):
        return FileType.IMAGE
    elif content_type in [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]:
        return FileType.DOCUMENT
    return FileType.OTHER


async def validate_file(file: UploadFile) -> Tuple[str, str, int]:
    """
    Validate file extension, content type, and size
    Returns content_type, extension, size
    """
    contents = await file.read()
    await file.seek(0)

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file"
        )

    size = len(contents)
    if size > settings.MAX_UPLOAD_SIZE:
        max_size_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size allowed is {max_size_mb} MB"
        )

    extension = Path(file.filename).suffix.lower()
    if extension not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS)}"
        )

    content_type = file.content_type

    return content_type, extension, size


async def upload_file_to_s3(
        file: UploadFile,
        user_id: int,
        review_id: Optional[int] = None,
        description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload a file to S3 and return metadata
    """
    try:
        content_type, extension, size = await validate_file(file)

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4().hex)
        clean_filename = Path(file.filename).stem.replace(" ", "_")
        safe_filename = f"{timestamp}_{user_id}_{unique_id}_{clean_filename}{extension}"

        file_type = determine_file_type(content_type)
        folder_path = f"{file_type.value}s"

        s3_key = f"{folder_path}/{safe_filename}"

        # Upload to S3
        s3_client = get_s3_client()
        await file.seek(0)
        s3_client.upload_fileobj(
            file.file,
            settings.AWS_BUCKET_NAME,
            s3_key,
            ExtraArgs={
                "ContentType": content_type
            }
        )

        file_url = f"{settings.AWS_S3_ENDPOINT}/{settings.AWS_BUCKET_NAME}/{s3_key}"

        return {
            "filename": safe_filename,
            "original_filename": file.filename,
            "file_type": file_type,
            "file_size": size,
            "content_type": content_type,
            "s3_key": s3_key,
            "s3_bucket": settings.AWS_BUCKET_NAME,
            "file_url": file_url,
            "user_id": user_id,
            "review_id": review_id,
            "description": description
        }

    except ClientError as e:
        logger.error(f"Error uploading file to S3: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage"
        )


def delete_file_from_s3(s3_key: str, bucket: str = None) -> bool:
    """
    Delete a file from S3
    """
    if not bucket:
        bucket = settings.AWS_BUCKET_NAME

    try:
        s3_client = get_s3_client()
        s3_client.delete_object(Bucket=bucket, Key=s3_key)
        return True
    except ClientError as e:
        logger.error(f"Error deleting file from S3: {e}")
        return False


def generate_presigned_url(s3_key: str, expires_in: int = 3600) -> str | None:
    """
    Generate a presigned URL for direct S3 access
    """
    try:
        s3_client = get_s3_client()
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_BUCKET_NAME,
                'Key': s3_key
            },
            ExpiresIn=expires_in
        )
        return url
    except ClientError as e:
        logger.error(f"Error generating presigned URL: {e}")
        return None