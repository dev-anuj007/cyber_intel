import secrets
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.services.auth.dependencies import (
    AuthServiceDependencyContext,
    get_auth_dependency_context,
)
from src.services.auth.protocols import (
    IAuthService,
    IUserReader,
    IUserWriter,
)
from src.services.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from src.services.auth.types import (
    AuthResponse,
    SigninCommand,
    SignupCommand,
    UserResponse,
)
from src.services.database.database_service import DatabaseService
from src.services.database.dependencies import default_database_service
from src.services.logger.logger_service import BaseLogger


class AuthService(IAuthService):
    def __init__(
        self,
        context: Optional[AuthServiceDependencyContext] = None,
    ) -> None:
        self.context: AuthServiceDependencyContext = (
            context or get_auth_dependency_context()
        )
        self._reader: IUserReader = self.context.reader
        self._writer: IUserWriter = self.context.writer
        self._logger: BaseLogger = self.context.logger
        self.jwt_secret = self.context.jwt_secret
        self.db_path = (
            Path(self.context.db_path)
            if isinstance(self.context.db_path, str)
            else self.context.db_path
        )
        self._local_db_service = (
            DatabaseService(db_path=self.db_path)
            if self.db_path is not None
            else None
        )

    # -------------------------------------------------------------------------
    # Public API Methods
    # -------------------------------------------------------------------------

    def signup(self, command: SignupCommand) -> AuthResponse:
        email = (command.email or "").strip().lower()
        password = command.password or ""
        if not email or "@" not in email or "." not in email:
            raise ValueError("A valid email address is required")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")

        with self._logger.span("auth.signup", email=email):
            with self._connection() as conn:
                existing = self._reader.get_user_by_email(conn, email)
                if existing:
                    self._logger.warning(
                        "Signup rejected: user already exists", email=email
                    )
                    raise ValueError(
                        "An account with this email address already exists"
                    )

                pwd_hash, salt = hash_password(password)
                user_id = self._writer.create_user(
                    conn,
                    email=email,
                    password_hash=pwd_hash,
                    salt=salt,
                    full_name=command.full_name,
                    role=command.role,
                )
                if conn is not None and hasattr(conn, "commit"):
                    conn.commit()

                user = self._reader.get_user_by_id(conn, user_id)
                if not user:
                    raise ValueError("Failed to retrieve created user")

                token = create_access_token(user["id"], user["email"])
                self._logger.info(
                    "User registered successfully",
                    user_id=user_id,
                    email=email,
                )
                return AuthResponse(
                    token=token,
                    user=self.format_user_response(user),
                )

    def signin(self, command: SigninCommand) -> AuthResponse:
        email = (command.email or "").strip().lower()
        password = command.password or ""

        with self._logger.span("auth.signin", email=email):
            with self._connection() as conn:
                user = self._reader.get_user_by_email(conn, email)
                if not user or not verify_password(
                    password,
                    user.get("salt", ""),
                    user.get("password_hash", ""),
                ):
                    self._logger.warning(
                        "Signin failed: invalid credentials", email=email
                    )
                    raise PermissionError("Invalid email or password")

                token = create_access_token(user["id"], user["email"])
                self._logger.info(
                    "User authenticated successfully",
                    user_id=user["id"],
                    email=email,
                )
                return AuthResponse(
                    token=token,
                    user=self.format_user_response(user),
                )

    def get_user_from_token(self, token: str) -> Optional[UserResponse]:
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            return None
        user_id = payload["sub"]

        with self._connection() as conn:
            user = self._reader.get_user_by_id(conn, user_id)
            if not user:
                return None
            return self.format_user_response(user)

    def verify_token(self, token: str) -> Optional[dict]:
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            return None
        return {
            "id": payload["sub"],
            "email": payload.get("email", ""),
            "sub": payload["sub"],
        }

    def get_user_by_id(self, user_id: Any) -> Optional[UserResponse]:
        with self._connection() as conn:
            user = self._reader.get_user_by_id(conn, user_id)
            if not user:
                return None
            return self.format_user_response(user)

    def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        with self._connection() as conn:
            user = self._reader.get_user_by_email(conn, email)
            if not user:
                return None
            return self.format_user_response(user)

    def get_user_api_key(self, user_id: Any) -> Optional[str]:
        with self._connection() as conn:
            u = self._reader.get_user_by_id(conn, user_id)
            if u:
                return u.get("gemini_api_key") or u.get("api_key")
            return None

    def set_user_api_key(self, user_id: Any, api_key: str) -> UserResponse:
        clean_key = api_key.strip()
        if not clean_key:
            raise ValueError("API key cannot be empty")

        with self._logger.span("auth.set_api_key", user_id=str(user_id)):
            with self._connection() as conn:
                self._writer.update_user_api_key(conn, user_id, clean_key)
                if conn is not None and hasattr(conn, "commit"):
                    conn.commit()
                updated = self._reader.get_user_by_id(conn, user_id)
                if not updated:
                    raise LookupError("User not found")
                self._logger.info("User API key configured", user_id=str(user_id))
                return self.format_user_response(updated)

    def delete_user_api_key(self, user_id: Any) -> UserResponse:
        with self._logger.span("auth.delete_api_key", user_id=str(user_id)):
            with self._connection() as conn:
                self._writer.update_user_api_key(conn, user_id, None)
                if conn is not None and hasattr(conn, "commit"):
                    conn.commit()
                updated = self._reader.get_user_by_id(conn, user_id)
                if not updated:
                    raise LookupError("User not found")
                self._logger.info("User API key cleared", user_id=str(user_id))
                return self.format_user_response(updated)

    def create_api_key(self, user_id: Any) -> str:
        key = f"sk-{secrets.token_hex(16)}"
        with self._connection() as conn:
            self._writer.update_api_key(conn, user_id, key)
            if conn is not None and hasattr(conn, "commit"):
                conn.commit()
        return key

    def verify_api_key(self, api_key: str) -> Optional[UserResponse]:
        with self._connection() as conn:
            user = self._reader.get_user_by_api_key(conn, api_key)
            if not user:
                return None
            return self.format_user_response(user)

    def list_api_keys(self, user_id: Any) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            u = self._reader.get_user_by_id(conn, user_id)
            if u and (u.get("gemini_api_key") or u.get("api_key")):
                k = u.get("gemini_api_key") or u.get("api_key")
                return [{"api_key": k, "created_at": u.get("created_at")}]
            return []

    def revoke_api_key(
        self, user_id: Any, api_key: Optional[str] = None
    ) -> bool:
        with self._connection() as conn:
            self._writer.delete_api_key(conn, user_id, api_key)
            if conn is not None and hasattr(conn, "commit"):
                conn.commit()
            return True

    def format_user_response(self, user: dict) -> UserResponse:
        api_key = user.get("gemini_api_key") or user.get("api_key")
        preview = None
        if api_key:
            if len(api_key) > 8:
                preview = f"{api_key[:6]}...{api_key[-4:]}"
            else:
                preview = "******"

        return UserResponse(
            id=int(user["id"]),
            email=user["email"],
            has_api_key=bool(api_key),
            api_key_preview=preview,
            created_at=user.get("created_at"),
            full_name=user.get("full_name"),
            role=user.get("role"),
        )

    # -------------------------------------------------------------------------
    # Private / Internal Helpers
    # -------------------------------------------------------------------------

    @contextmanager
    def _connection(self):
        svc = (
            self._local_db_service
            if self._local_db_service is not None
            else default_database_service
        )
        with svc.get_connection() as conn:
            yield conn


default_auth_service: IAuthService = AuthService()
