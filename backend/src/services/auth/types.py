from typing import Protocol, Optional, Dict, Any, List
import sqlite3
from pydantic import BaseModel


class UserSignupRequest(BaseModel):
    email: str
    password: str


class UserSigninRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    has_api_key: bool
    api_key_preview: Optional[str] = None
    created_at: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class ApiKeyUpdateRequest(BaseModel):
    api_key: str



class IUserReader(Protocol):
    """User data reader contract."""

    def get_user_by_email(self, conn: sqlite3.Connection, email: str) -> Optional[dict]:
        ...

    def get_user_by_id(self, conn: sqlite3.Connection, user_id: int) -> Optional[dict]:
        ...


class IUserWriter(Protocol):
    """User data writer contract."""

    def create_user(self, conn: sqlite3.Connection, email: str, password_hash: str, salt: str) -> int:
        ...

    def update_user_api_key(self, conn: sqlite3.Connection, user_id: int, api_key: Optional[str]) -> bool:
        ...


class IAuthService(Protocol):
    """Auth business service contract."""

    def format_user_response(self, user: dict) -> UserResponse:
        ...

    def signup(self, req: UserSignupRequest) -> AuthResponse:
        ...

    def signin(self, req: UserSigninRequest) -> AuthResponse:
        ...

    def get_user_from_token(self, token: str) -> Optional[dict]:
        ...

    def set_user_api_key(self, user_id: int, api_key: str) -> UserResponse:
        ...

    def delete_user_api_key(self, user_id: int) -> UserResponse:
        ...
