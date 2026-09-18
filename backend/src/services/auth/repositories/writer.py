import sqlite3
from typing import Optional
from src.services.auth.types import IUserWriter


class UserWriter(IUserWriter):

    def create_user(self, conn: sqlite3.Connection, email: str, password_hash: str, salt: str) -> int:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, password_hash, salt) VALUES (?, ?, ?)",
            (email.strip().lower(), password_hash, salt),
        )
        return cursor.lastrowid

    def update_user_api_key(self, conn: sqlite3.Connection, user_id: int, api_key: Optional[str]) -> bool:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET gemini_api_key = ? WHERE id = ?",
            (api_key.strip() if api_key else None, user_id),
        )
        return cursor.rowcount > 0
