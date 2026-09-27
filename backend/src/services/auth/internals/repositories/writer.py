from typing import Any, Optional

from sqlmodel import Session, col, select

from src.services.auth.internals.repositories.models import UserTable
from src.services.auth.protocols import IUserWriter
from src.services.database.dependencies import get_db_session


def _get_session(conn: Any) -> Session:
    return get_db_session(conn=conn)


class UserWriter(IUserWriter):
    def create_user(
        self,
        conn: Optional[Any],
        email: str,
        password_hash: str,
        salt: str = "",
        full_name: Optional[str] = None,
        role: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        if conn is None:
            raise ValueError("Database connection required")
        with _get_session(conn) as session:
            new_user = UserTable(
                email=email.strip().lower(),
                password_hash=password_hash,
                salt=salt,
                full_name=full_name,
                role=role or "member",
            )
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            if new_user.id is None:
                raise ValueError("Failed to obtain created user ID")
            return new_user.id

    def update_last_login(self, conn: Optional[Any], user_id: Any) -> bool:
        return True

    def update_user_api_key(self, conn: Optional[Any], user_id: Any, api_key: Optional[str]) -> bool:
        if conn is None or user_id is None:
            return False
        try:
            target_id = int(user_id)
        except (ValueError, TypeError):
            target_id = user_id
        with _get_session(conn) as session:
            user = session.exec(select(UserTable).where(col(UserTable.id) == target_id)).first()
            if not user:
                return False
            user.gemini_api_key = api_key.strip() if api_key else None
            session.add(user)
            session.commit()
            return True

    def update_api_key(self, conn: Optional[Any], user_id: Any, api_key: Optional[str]) -> bool:
        return self.update_user_api_key(conn, user_id, api_key)

    def delete_api_key(self, conn: Optional[Any], user_id: Any, api_key: Optional[str] = None) -> bool:
        return self.update_user_api_key(conn, user_id, None)



