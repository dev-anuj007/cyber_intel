import sqlite3
from typing import Optional
from src.services.auth.types import IUserReader


class UserReader(IUserReader):

    def get_user_by_email(self, conn: sqlite3.Connection, email: str) -> Optional[dict]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, password_hash, salt, gemini_api_key, created_at FROM users WHERE email = ?",
            (email.strip().lower(),),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "email": row[1],
            "password_hash": row[2],
            "salt": row[3],
            "gemini_api_key": row[4],
            "created_at": str(row[5]),
        }

    def get_user_by_id(self, conn: sqlite3.Connection, user_id: int) -> Optional[dict]:
        """Fetch user record by ID."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, password_hash, salt, gemini_api_key, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "email": row[1],
            "password_hash": row[2],
            "salt": row[3],
            "gemini_api_key": row[4],
            "created_at": str(row[5]),
        }
