from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.crud.base import CRUDBase
from app.models import User
from app.models.user import User, EmailChangeVerification
from app.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        db_obj = User(
            email=obj_in.email,
            hashed_password=get_password_hash(obj_in.password),
            first_name=obj_in.first_name,
            last_name=obj_in.last_name,
            is_active=obj_in.is_active,
            is_admin=obj_in.is_admin,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
            self, db: Session, *, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)

        if "password" in update_data and update_data["password"]:
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password

        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def authenticate(self, db: Session, *, email: str, password: str) -> Optional[User]:
        user = self.get_by_email(db, email=email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def is_active(self, user: User) -> bool:
        return user.is_active

    def is_admin(self, user: User) -> bool:
        return user.is_admin

    def verify_email(self, db: Session, *, user_id: int) -> User:
        user = self.get(db, id=user_id)
        if user:
            user.is_verified = True
            user.verification_token = None
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    def set_verification_token(
            self, db: Session, *, user_id: int, token: str
    ) -> User:
        user = self.get(db, id=user_id)
        if user:
            user.verification_token = token
            user.verification_sent_at = datetime.now(timezone.utc)
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    def set_password_reset_token(
            self, db: Session, *, user_id: int, token: str
    ) -> User:
        user = self.get(db, id=user_id)
        if user:
            user.password_reset_token = token
            user.password_reset_at = datetime.now(timezone.utc)
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    def reset_password(
            self, db: Session, *, user_id: int, new_password: str
    ) -> User:
        user = self.get(db, id=user_id)
        if user:
            hashed_password = get_password_hash(new_password)
            user.hashed_password = hashed_password
            user.password_reset_token = None
            user.password_reset_at = None
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    def get_by_oauth_id(self, db: Session, *, provider: str, oauth_id: str) -> Optional[User]:
        return db.query(User).filter(
            User.oauth_provider == provider,
            User.oauth_id == oauth_id
        ).first()

    def update_oauth_info(
            self, db: Session, *, user_id: int, provider: str, oauth_id: str, oauth_data: str
    ) -> User:
        user = self.get(db, id=user_id)
        if user:
            user.oauth_provider = provider
            user.oauth_id = oauth_id
            user.oauth_data = oauth_data
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    def create_oauth_user(
            self, db: Session, *, email: str, first_name: str, last_name: str,
            profile_image: Optional[str], provider: str, oauth_id: str, oauth_data: str,
            is_verified: bool = False
    ) -> User:
        import secrets
        import string
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))

        db_obj = User(
            email=email,
            hashed_password=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            profile_image=profile_image,
            is_active=True,
            is_verified=is_verified,
            oauth_provider=provider,
            oauth_id=oauth_id,
            oauth_data=oauth_data
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_email_change_verification(
            self, db: Session, *, user_id: int, new_email: str
    ) -> EmailChangeVerification:
        import secrets
        import string
        from datetime import datetime, timedelta

        verification_code = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(6))

        expires_at = datetime.now() + timedelta(hours=24)

        db.query(EmailChangeVerification).filter(
            EmailChangeVerification.user_id == user_id
        ).delete()

        db_obj = EmailChangeVerification(
            user_id=user_id,
            new_email=new_email,
            verification_code=verification_code,
            expires_at=expires_at
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def verify_email_change(
            self, db: Session, *, user_id: int, verification_code: str
    ) -> Optional[EmailChangeVerification]:
        from datetime import datetime

        verification = db.query(EmailChangeVerification).filter(
            EmailChangeVerification.user_id == user_id,
            EmailChangeVerification.verification_code == verification_code,
            EmailChangeVerification.expires_at > datetime.now()
        ).first()

        return verification

    def complete_email_change(
            self, db: Session, *, user_id: int, new_email: str
    ) -> User | None:
        user = self.get(db, id=user_id)
        if not user:
            return None

        user.email = new_email
        db.add(user)

        db.query(EmailChangeVerification).filter(
            EmailChangeVerification.user_id == user_id
        ).delete()

        db.commit()
        db.refresh(user)
        return user

user = CRUDUser(User)