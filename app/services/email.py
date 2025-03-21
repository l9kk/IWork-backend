import logging
import os
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import SessionLocal

logger = logging.getLogger(__name__)

templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "email-templates")
os.makedirs(templates_dir, exist_ok=True)

env = Environment(
    loader=FileSystemLoader(templates_dir),
    autoescape=select_autoescape(['html', 'xml'])
)

# Email connection configuration
conf = ConnectionConfig(
    MAIL_USERNAME=settings.SMTP_USER,
    MAIL_PASSWORD=settings.SMTP_PASSWORD,
    MAIL_FROM=settings.EMAILS_FROM_EMAIL,
    MAIL_PORT=settings.SMTP_PORT,
    MAIL_SERVER=settings.SMTP_HOST,
    MAIL_FROM_NAME=settings.EMAILS_FROM_NAME,
    MAIL_STARTTLS=settings.SMTP_TLS,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(templates_dir)
)


@contextmanager
def get_email_db_session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error in email session: {e}")
        raise
    finally:
        db.close()


async def send_email(
        email_to: List[str],
        subject: str,
        template_name: str,
        template_data: Dict[str, Any],
) -> None:
    """
    Send an email using the provided template and data.
    """
    if not settings.EMAILS_ENABLED:
        logger.info(f"Emails disabled, would have sent {subject} to {email_to}")
        return

    try:
        template_data["settings"] = settings

        template = env.get_template(f"{template_name}")
        html_content = template.render(**template_data)

        message = MessageSchema(
            subject=subject,
            recipients=email_to,
            body=html_content,
            subtype=MessageType.html
        )

        fm = FastMail(conf)
        await fm.send_message(message)
        logger.info(f"Email sent: {subject} to {email_to}")
    except ConnectionErrors as e:
        logger.error(f"Failed to send email: {e}")
    except Exception as e:
        logger.error(f"Error sending email: {e}")


def generate_verification_token(user_id: int) -> str:
    """
    Generate a verification token for email verification.
    """

    expires_delta = timedelta(hours=settings.VERIFICATION_TOKEN_EXPIRE_HOURS)
    return create_access_token(
        subject=user_id,
        expires_delta=expires_delta,
        jti=f"verification_{user_id}"
    )


def generate_password_reset_token(user_id: int) -> str:
    """
    Generate a token for password reset.
    """
    expires_delta = timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    return create_access_token(
        subject=user_id,
        expires_delta=expires_delta,
        jti=f"password_reset_{user_id}"
    )


async def send_verification_email(user_email: str, user_first_name: str, user_id: int) -> None:
    """
    Send an email verification link to the user.
    """
    verification_token = generate_verification_token(user_id)

    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"

    subject = "Verify your email address"
    template_data = {
        "user": {"first_name": user_first_name},
        "verification_url": verification_url,
        "expire_hours": settings.VERIFICATION_TOKEN_EXPIRE_HOURS
    }

    with get_email_db_session() as db:
        from app import crud
        crud.user.set_verification_token(db, user_id=user_id, token=verification_token)

    await send_email(
        email_to=[user_email],
        subject=subject,
        template_name="verification.html",
        template_data=template_data
    )


async def send_password_reset_email(user_email: str, user_first_name: str, user_id: int) -> None:
    """
    Send a password reset link to the user.
    """
    password_reset_token = generate_password_reset_token(user_id)

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={password_reset_token}"

    subject = "Reset your password"
    template_data = {
        "user": {"first_name": user_first_name},
        "reset_url": reset_url,
        "expire_hours": settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
    }

    with get_email_db_session() as db:
        from app import crud
        crud.user.set_password_reset_token(db, user_id=user_id, token=password_reset_token)

    await send_email(
        email_to=[user_email],
        subject=subject,
        template_name="reset_password.html",
        template_data=template_data
    )


async def send_review_approved_email(user_email: str, user_first_name: str, company_name: str, review_id: int) -> None:
    """
    Send a notification email when a review is approved.
    """
    review_url = f"{settings.FRONTEND_URL}/reviews/{review_id}"

    subject = "Your review has been approved"
    template_data = {
        "user": {"first_name": user_first_name},
        "company_name": company_name,
        "review_url": review_url
    }

    await send_email(
        email_to=[user_email],
        subject=subject,
        template_name="review_approved.html",
        template_data=template_data
    )


async def send_review_rejected_email(
        user_email: str,
        user_first_name: str,
        company_name: str,
        rejection_reason: str
) -> None:
    """
    Send a notification email when a review is rejected.
    """
    subject = "Your review requires changes"
    template_data = {
        "user": {"first_name": user_first_name},
        "company_name": company_name,
        "rejection_reason": rejection_reason
    }

    await send_email(
        email_to=[user_email],
        subject=subject,
        template_name="review_rejected.html",
        template_data=template_data
    )