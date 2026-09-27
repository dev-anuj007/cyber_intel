from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from src.services.auth.types import (
    AuthResponse,
    SigninCommand,
    SignupCommand,
    UserResponse,
)


@runtime_checkable
class IUserReader(Protocol):
    def get_user_by_email(
        self, conn: Optional[Any], email: str
    ) -> Optional[dict]: ...

    def get_user_by_id(
        self, conn: Optional[Any], user_id: Any
    ) -> Optional[dict]: ...

    def get_user_by_api_key(
        self, conn: Optional[Any], api_key: str
    ) -> Optional[dict]: ...


@runtime_checkable
class IUserWriter(Protocol):
    def create_user(
        self,
        conn: Optional[Any],
        email: str,
        password_hash: str,
        salt: str = "",
        full_name: Optional[str] = None,
        role: Optional[str] = None,
        **kwargs: Any,
    ) -> int: ...

    def update_user_api_key(
        self, conn: Optional[Any], user_id: Any, api_key: Optional[str]
    ) -> bool: ...

    def update_api_key(
        self, conn: Optional[Any], user_id: Any, api_key: Optional[str]
    ) -> bool: ...

    def delete_api_key(
        self,
        conn: Optional[Any],
        user_id: Any,
        api_key: Optional[str] = None,
    ) -> bool: ...

    def update_last_login(self, conn: Optional[Any], user_id: Any) -> bool: ...


@runtime_checkable
class IAuthService(Protocol):
    def format_user_response(self, user: dict) -> UserResponse: ...

    def signup(self, command: SignupCommand) -> AuthResponse: ...

    def signin(self, command: SigninCommand) -> AuthResponse: ...

    def verify_token(self, token: str) -> Optional[dict]: ...

    def get_user_from_token(self, token: str) -> Optional[UserResponse]: ...

    def get_user_by_id(self, user_id: Any) -> Optional[UserResponse]: ...

    def get_user_by_email(self, email: str) -> Optional[UserResponse]: ...

    def create_api_key(self, user_id: Any) -> str: ...

    def verify_api_key(self, api_key: str) -> Optional[UserResponse]: ...

    def list_api_keys(self, user_id: Any) -> List[Dict[str, Any]]: ...

    def revoke_api_key(
        self, user_id: Any, api_key: Optional[str] = None
    ) -> bool: ...

    def get_user_api_key(self, user_id: Any) -> Optional[str]: ...

    def set_user_api_key(self, user_id: Any, api_key: str) -> UserResponse: ...

    def delete_user_api_key(self, user_id: Any) -> UserResponse: ...
