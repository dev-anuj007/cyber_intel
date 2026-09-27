from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from fastapi import Depends, Header

from src.core.exceptions import AuthenticationError
from src.services.auth.internals.repositories.reader import UserReader
from src.services.auth.internals.repositories.writer import UserWriter
from src.services.auth.protocols import (
    IAuthService,
    IUserReader,
    IUserWriter,
)
from src.services.logger.context import update_journey_context


@dataclass(frozen=True)
class AuthServiceDependencyContext:
    reader: IUserReader
    writer: IUserWriter
    jwt_secret: Optional[str] = None
    db_path: Optional[Union[Path, str]] = None


def get_auth_dependency_context(
    db_path: Optional[Union[Path, str]] = None,
    reader: Optional[IUserReader] = None,
    writer: Optional[IUserWriter] = None,
    jwt_secret: Optional[str] = None,
) -> AuthServiceDependencyContext:
    return AuthServiceDependencyContext(
        reader=reader if reader is not None else UserReader(),
        writer=writer if writer is not None else UserWriter(),
        jwt_secret=jwt_secret,
        db_path=db_path,
    )


def create_auth_service(
    context: Optional[AuthServiceDependencyContext] = None,
    **kwargs: Any,
) -> IAuthService:
    from src.services.auth.auth_service import AuthService

    if context is None:
        context = get_auth_dependency_context(**kwargs)
    return AuthService(context=context)


_default_auth_service: Optional[IAuthService] = None


def get_auth_service() -> IAuthService:
    global _default_auth_service
    if _default_auth_service is None:
        _default_auth_service = create_auth_service()
    return _default_auth_service


class _LazyAuthServiceProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_auth_service(), name)


default_auth_service: IAuthService = _LazyAuthServiceProxy()  # type: ignore



def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    auth_service: IAuthService = Depends(get_auth_service),
) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    user = auth_service.get_user_from_token(token)
    if user:
        update_journey_context(user_id=user["id"], user_email=user["email"])
    return user


def get_current_user(
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> dict:
    if not current_user:
        raise AuthenticationError(
            message="Authentication required or invalid/expired session token",
            code="UNAUTHENTICATED",
        )
    return current_user



