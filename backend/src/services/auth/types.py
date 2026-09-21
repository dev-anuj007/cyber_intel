from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserSignupRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "member"


class UserSigninRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: Any
    email: str
    has_api_key: bool = False
    api_key_preview: Optional[str] = None
    created_at: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None

    def __getitem__(self, item):
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def __contains__(self, item):
        return hasattr(self, item) and getattr(self, item) is not None

    def get(self, item, default=None):
        try:
            return self[item]
        except KeyError:
            return default

    def keys(self):
        return ["id", "email", "has_api_key", "api_key_preview", "created_at", "full_name", "role"]


class AuthResponse(BaseModel):
    token: str
    user: UserResponse

    def __getitem__(self, item):
        if item == "token":
            return self.token
        if item == "user":
            return self.user
        if hasattr(self.user, item):
            return getattr(self.user, item)
        raise KeyError(item)

    def __contains__(self, item):
        return item in ("token", "user") or (hasattr(self.user, item) and getattr(self.user, item) is not None)

    def get(self, item, default=None):
        try:
            return self[item]
        except KeyError:
            return default

    def keys(self):
        return ["token", "user"]


class ApiKeyUpdateRequest(BaseModel):
    api_key: Optional[str] = None


class IUserReader(Protocol):
    """User data reader contract."""

    def get_user_by_email(self, conn: Optional[Any], email: str) -> Optional[dict]: ...

    def get_user_by_id(self, conn: Optional[Any], user_id: Any) -> Optional[dict]: ...

    def get_user_by_api_key(self, conn: Optional[Any], api_key: str) -> Optional[dict]: ...


class IUserWriter(Protocol):
    """User data writer contract."""

    def create_user(
        self,
        conn: Optional[Any],
        email: str,
        password_hash: str,
        salt: str = "",
        full_name: Optional[str] = None,
        role: Optional[str] = None,
        **kwargs: Any,
    ) -> Any: ...

    def update_user_api_key(self, conn: Optional[Any], user_id: Any, api_key: Optional[str]) -> bool: ...

    def update_api_key(self, conn: Optional[Any], user_id: Any, api_key: Optional[str]) -> bool: ...

    def delete_api_key(
        self, conn: Optional[Any], user_id: Any, api_key: Optional[str] = None
    ) -> bool: ...

    def update_last_login(self, conn: Optional[Any], user_id: Any) -> bool: ...


class IAuthService(Protocol):
    """Auth business service contract."""

    def format_user_response(self, user: dict) -> UserResponse: ...

    def signup(self, req: UserSignupRequest) -> AuthResponse: ...

    def signin(self, req: UserSigninRequest) -> AuthResponse: ...

    def get_user_from_token(self, token: str) -> Optional[dict]: ...

    def set_user_api_key(self, user_id: int, api_key: str) -> UserResponse: ...

    def delete_user_api_key(self, user_id: int) -> UserResponse: ...
