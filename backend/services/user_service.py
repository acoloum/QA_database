"""使用者安全狀態異動服務。"""

from ..extensions import db
from ..models import User
from ..utils import hash_password, log_audit


class UserService:
    """以單一 transaction 保存帳號異動、token 撤銷版本與 audit。"""

    @staticmethod
    def _find(user_id: int) -> User | None:
        return db.session.get(User, user_id)

    @staticmethod
    def set_active(actor_user_id: int, user_id: int, is_active: bool) -> User | None:
        try:
            user = UserService._find(user_id)
            if user is None:
                return None
            old_value = {
                'is_active': user.is_active,
                'token_version': user.token_version,
            }
            user.is_active = is_active
            user.token_version += 1
            log_audit(
                actor_user_id,
                'update_active',
                'USER',
                record_id=user.id,
                old_val=old_value,
                new_val={
                    'is_active': user.is_active,
                    'token_version': user.token_version,
                },
            )
            db.session.commit()
            return user
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def set_role(actor_user_id: int, user_id: int, role: str) -> User | None:
        try:
            user = UserService._find(user_id)
            if user is None:
                return None
            old_value = {
                'role': user.role,
                'token_version': user.token_version,
            }
            user.role = role
            user.token_version += 1
            log_audit(
                actor_user_id,
                'update_role',
                'USER',
                record_id=user.id,
                old_val=old_value,
                new_val={
                    'role': user.role,
                    'token_version': user.token_version,
                },
            )
            db.session.commit()
            return user
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def reset_password(actor_user_id: int, user_id: int, password: str) -> User | None:
        try:
            user = UserService._find(user_id)
            if user is None:
                return None
            old_version = user.token_version
            user.password = hash_password(password)
            user.token_version += 1
            log_audit(
                actor_user_id,
                'reset_password',
                'USER',
                record_id=user.id,
                old_val={'token_version': old_version},
                new_val={'token_version': user.token_version},
            )
            db.session.commit()
            return user
        except Exception:
            db.session.rollback()
            raise
