import os

from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional, List, Union, Dict

load_dotenv()

class Settings(BaseModel):
    PROJECT_NAME: str = "IWork API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT")
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
    AI_SCANNER_THRESHOLD: float = float(os.getenv("AI_SCANNER_THRESHOLD"))

    # Email settings
    SMTP_SERVER: Optional[str] = os.getenv("SMTP_SERVER")
    SMTP_PORT: Optional[int] = int(os.getenv("SMTP_PORT"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    EMAIL_FROM: Optional[str] = os.getenv("EMAIL_FROM")

    # Security settings
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS").split(",")
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "True").lower() == "true"

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    RATE_LIMIT_DEFAULT: str = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()