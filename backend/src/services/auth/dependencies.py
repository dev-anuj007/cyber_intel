from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from fastapi import Depends, Header

from src.core.exceptions import AuthenticationError
from src.services.auth.internals.repositories.reader import UserReader
from src.services.auth.internals.repositories.writer import UserWriter
from src.services.auth.protocols import (
    IAuthService,
    IUserReader,
    IUserWriter,
)
from src.services.auth.types import (
    AuthResponse,
    SigninCommand,
    SignupCommand,
    UserResponse,
)
from src.services.logger.context import update_journey_context
from src.services.logger.logger_service import BaseLogger, get_logger

if TYPE_CHECKING:
    pass


@dataclass
class AuthServiceDependencyContext:
    reader: IUserReader
    writer: IUserWriter
    logger: BaseLogger
    jwt_secret: Optional[str] = None
    db_path: Optional[Union[Path, str]] = None


def get_auth_dependency_context(
    db_path: Optional[Union[Path, str]] = None,
    reader: Optional[IUserReader] = None,
    writer: Optional[IUserWriter] = None,
    jwt_secret: Optional[str] = None,
    logger: Optional[BaseLogger] = None,
) -> AuthServiceDependencyContext:
    return AuthServiceDependencyContext(
        reader=reader if reader is not None else UserReader(),
        writer=writer if writer is not None else UserWriter(),
        logger=logger or get_logger("services.auth"),
        jwt_secret=jwt_secret,
        db_path=db_path,
    )


@lru_cache()
def get_auth_service() -> IAuthService:
    from src.services.auth.auth_service import AuthService

    return AuthService()


def create_auth_service(
    context: Optional[AuthServiceDependencyContext] = None,
    db_path: Optional[Union[Path, str]] = None,
    reader: Optional[IUserReader] = None,
    writer: Optional[IUserWriter] = None,
    jwt_secret: Optional[str] = None,
    logger: Optional[BaseLogger] = None,
) -> IAuthService:
    from src.services.auth.auth_service import AuthService

    if context is not None:
        return AuthService(context=context)
    return AuthService(
        context=get_auth_dependency_context(
            db_path=db_path,
            reader=reader,
            writer=writer,
            jwt_secret=jwt_secret,
            logger=logger,
        )
    )


class _LazyAuthServiceProxy(IAuthService):
    """Lazy Singleton Proxy for AuthService."""

    def __init__(self) -> None:
        self._instance: Optional[IAuthService] = None

    def _get_service(self) -> IAuthService:
        if self._instance is None:
            self._instance = get_auth_service()
        return self._instance

    def format_user_response(self, user: dict) -> UserResponse:
        return self._get_service().format_user_response(user)

    def signup(self, command: SignupCommand) -> AuthResponse:
        return self._get_service().signup(command)

    def signin(self, command: SigninCommand) -> AuthResponse:
        return self._get_service().signin(command)

    def verify_token(self, token: str) -> Optional[dict]:
        return self._get_service().verify_token(token)

    def get_user_from_token(self, token: str) -> Optional[UserResponse]:
        return self._get_service().get_user_from_token(token)

    def get_user_by_id(self, user_id: Any) -> Optional[UserResponse]:
        return self._get_service().get_user_by_id(user_id)

    def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        return self._get_service().get_user_by_email(email)

    def create_api_key(self, user_id: Any) -> str:
        return self._get_service().create_api_key(user_id)

    def verify_api_key(self, api_key: str) -> Optional[UserResponse]:
        return self._get_service().verify_api_key(api_key)

    def list_api_keys(self, user_id: Any) -> List[Dict[str, Any]]:
        return self._get_service().list_api_keys(user_id)

    def revoke_api_key(
        self, user_id: Any, api_key: Optional[str] = None
    ) -> bool:
        return self._get_service().revoke_api_key(user_id, api_key)

    def get_user_api_key(self, user_id: Any) -> Optional[str]:
        return self._get_service().get_user_api_key(user_id)

    def set_user_api_key(self, user_id: Any, api_key: str) -> UserResponse:
        return self._get_service().set_user_api_key(user_id, api_key)

    def delete_user_api_key(self, user_id: Any) -> UserResponse:
        return self._get_service().delete_user_api_key(user_id)


default_auth_service: IAuthService = _LazyAuthServiceProxy()


def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    auth_service: IAuthService = Depends(get_auth_service),
) -> Optional[UserResponse]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    user = auth_service.get_user_from_token(token)
    if user:
        update_journey_context(user_id=str(user.id), user_email=user.email)
    return user


def get_current_user(
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
) -> UserResponse:
    if not current_user:
        raise AuthenticationError(
            message="Authentication required or invalid/expired session token",
            code="UNAUTHENTICATED",
        )
    return current_user
