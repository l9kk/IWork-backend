import os

from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional, List, Union, Dict

load_dotenv()

class Settings(BaseModel):
    PROJECT_NAME: str = "IWork API"
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS"))
    DEBUG: bool = os.getenv("DEBUG").lower() == "true"
    ALLOWED_HOSTS: List[str] = os.getenv("ALLOWED_HOSTS").split(",")

    # Database settings - using Neon
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    SQLALCHEMY_DATABASE_URI: str = DATABASE_URL

    # Upstash Redis settings
    REDIS_URL: str = os.getenv("REDIS_URL")
    REDIS_TOKEN: str = os.getenv("REDIS_TOKEN")

    # AI Scanner settings
    AI_SCANNER_ENABLED: bool = os.getenv("AI_SCANNER_ENABLED").lower() == "true"

    # Email settings
    EMAILS_ENABLED: bool = os.getenv("EMAILS_ENABLED")
    SMTP_TLS: bool = os.getenv("SMTP_TLS")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT"))
    SMTP_HOST: str = os.getenv("SMTP_HOST")
    SMTP_USER: str = os.getenv("SMTP_USER")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD")
    EMAILS_FROM_EMAIL: str = os.getenv("EMAILS_FROM_EMAIL")
    EMAILS_FROM_NAME: str = os.getenv("EMAILS_FROM_NAME")

    # Frontend URLs
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    VERIFICATION_TOKEN_EXPIRE_HOURS: int = int(os.getenv("VERIFICATION_TOKEN_EXPIRE_HOURS"))
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_HOURS"))

    # Templates directory
    EMAIL_TEMPLATES_DIR: str = os.getenv("EMAIL_TEMPLATES_DIR", "app/email-templates")

    # Security settings
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS").split(",")
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "True").lower() == "true"

    # AWS S3 settings
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_BUCKET_NAME: str = os.getenv("AWS_BUCKET_NAME", "iwork-uploads")
    AWS_S3_ENDPOINT: str = os.getenv("AWS_S3_ENDPOINT", "https://s3.amazonaws.com")

    # Upload settings
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB default
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = os.getenv(
        "ALLOWED_UPLOAD_EXTENSIONS", ".jpg,.jpeg,.png,.gif,.pdf,.doc,.docx"
    ).split(",")

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()