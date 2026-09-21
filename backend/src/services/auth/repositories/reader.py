"""User Data Reader Repository with SQLModel ORM."""

from typing import Any, Optional

from sqlmodel import Session, col, or_, select

from src.services.auth.repositories.models import UserTable
from src.services.auth.types import IUserReader
from src.services.database import get_db_session


def _get_session(conn: Any) -> Session:
    return get_db_session(conn=conn)


class UserReader(IUserReader):
    def get_user_by_email(self, conn: Optional[Any], email: str) -> Optional[dict]:
        if conn is None:
            return None
        with _get_session(conn) as session:
            statement = select(UserTable).where(col(UserTable.email) == email.strip().lower())
            user = session.exec(statement).first()
            if not user:
                return None
            return {
                "id": user.id,
                "email": user.email,
                "password_hash": user.password_hash,
                "salt": user.salt,
                "full_name": user.full_name,
                "role": user.role,
                "gemini_api_key": user.gemini_api_key or user.api_key,
                "api_key": user.api_key or user.gemini_api_key,
                "created_at": str(user.created_at) if user.created_at else None,
            }

    def get_user_by_id(self, conn: Optional[Any], user_id: Any) -> Optional[dict]:
        """Fetch user record by ID."""
        if conn is None or user_id is None:
            return None
        try:
            target_id = int(user_id)
        except (ValueError, TypeError):
            target_id = user_id
        with _get_session(conn) as session:
            statement = select(UserTable).where(col(UserTable.id) == target_id)
            user = session.exec(statement).first()
            if not user:
                return None
            return {
                "id": user.id,
                "email": user.email,
                "password_hash": user.password_hash,
                "salt": user.salt,
                "full_name": user.full_name,
                "role": user.role,
                "gemini_api_key": user.gemini_api_key or user.api_key,
                "api_key": user.api_key or user.gemini_api_key,
                "created_at": str(user.created_at) if user.created_at else None,
            }

    def get_user_by_api_key(self, conn: Optional[Any], api_key: str) -> Optional[dict]:
        if conn is None:
            return None
        with _get_session(conn) as session:
            statement = select(UserTable).where(
                or_(
                    col(UserTable.gemini_api_key) == api_key.strip(),
                    col(UserTable.api_key) == api_key.strip(),
                )
            )
            user = session.exec(statement).first()
            if not user:
                return None
            return {
                "id": user.id,
                "email": user.email,
                "password_hash": user.password_hash,
                "salt": user.salt,
                "full_name": user.full_name,
                "role": user.role,
                "gemini_api_key": user.gemini_api_key or user.api_key,
                "api_key": user.api_key or user.gemini_api_key,
                "created_at": str(user.created_at) if user.created_at else None,
            }
