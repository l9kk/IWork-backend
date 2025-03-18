import asyncio
import logging
from datetime import datetime
from app.db.base import SessionLocal
from app import crud

logger = logging.getLogger(__name__)

async def cleanup_expired_tokens():
    """
    Scheduled task to clean up expired refresh tokens from the database
    """
    try:
        db = SessionLocal()
        crud.refresh_token.clean_expired_tokens(db)
        logger.info(f"Cleaned up expired tokens at {datetime.utcnow()}")
    except Exception as e:
        logger.error(f"Error cleaning up expired tokens: {e}")
    finally:
        db.close()

async def start_token_cleanup_scheduler():
    while True:
        await cleanup_expired_tokens()

        await asyncio.sleep(86400)  # 24 hours in seconds