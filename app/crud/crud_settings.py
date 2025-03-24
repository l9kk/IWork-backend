from typing import Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.settings import AccountSettings
from app.schemas.settings import AccountSettingsUpdate


class CRUDAccountSettings(CRUDBase[AccountSettings, AccountSettingsUpdate, AccountSettingsUpdate]):
    def get_by_user_id(self, db: Session, *, user_id: int) -> Optional[AccountSettings]:
        return db.query(AccountSettings).filter(AccountSettings.user_id == user_id).first()

    def create_or_update(
            self, db: Session, *, user_id: int, obj_in: AccountSettingsUpdate
    ) -> AccountSettings:
        db_obj = self.get_by_user_id(db, user_id=user_id)

        if db_obj:
            return self.update(db, db_obj=db_obj, obj_in=obj_in)
        else:
            obj_in_data = obj_in.dict(exclude_unset=True)
            db_obj = AccountSettings(user_id=user_id, **obj_in_data)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj


account_settings = CRUDAccountSettings(AccountSettings)