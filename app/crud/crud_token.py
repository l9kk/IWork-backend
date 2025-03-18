import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.token import RefreshToken
from app.schemas.token import RefreshTokenCreate


class CRUDRefreshToken(CRUDBase[RefreshToken, RefreshTokenCreate, RefreshTokenCreate]):
    def create_refresh_token(
            self, db: Session, *, user_id: int, expires_delta: timedelta,
            device_name: Optional[str] = None,
            device_ip: Optional[str] = None,
            user_agent: Optional[str] = None
    ) -> RefreshToken:
        token_value = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + expires_delta

        refresh_token = RefreshToken(
            user_id=user_id,
            token=token_value,
            expires_at=expires_at,
            device_name=device_name,
            device_ip=device_ip,
            user_agent=user_agent
        )

        db.add(refresh_token)
        db.commit()
        db.refresh(refresh_token)
        return refresh_token

    def get_by_token(self, db: Session, *, token: str) -> Optional[RefreshToken]:
        return db.query(RefreshToken).filter(RefreshToken.token == token).first()

    def is_valid(self, refresh_token: RefreshToken) -> bool:
        now = datetime.now(timezone.utc)
        return (not refresh_token.revoked and refresh_token.expires_at > now)

    def revoke_token(self, db: Session, *, token: str) -> None:
        refresh_token = self.get_by_token(db, token=token)
        if refresh_token:
            refresh_token.revoked = True
            db.add(refresh_token)
            db.commit()

    def revoke_all_user_tokens(self, db: Session, *, user_id: int) -> None:
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False
        ).update({"revoked": True})
        db.commit()

    def clean_expired_tokens(self, db: Session) -> None:
        now = datetime.now(timezone.utc)
        db.query(RefreshToken).filter(
            RefreshToken.expires_at < now
        ).delete()
        db.commit()


refresh_token = CRUDRefreshToken(RefreshToken)