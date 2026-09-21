import secrets
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional, Union

from src.services.auth.repositories.reader import UserReader
from src.services.auth.repositories.writer import UserWriter
from src.services.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from src.services.auth.types import (
    AuthResponse,
    IAuthService,
    IUserReader,
    IUserWriter,
    UserResponse,
    UserSigninRequest,
    UserSignupRequest,
)
from src.services.database import default_database_service
from src.services.database.database_service import DatabaseService
from src.services.logger import get_logger

logger = get_logger("services.auth")


class AuthService(IAuthService):
    def __init__(
        self,
        db_path: Optional[Union[Path, str]] = None,
        reader: Optional[IUserReader] = None,
        writer: Optional[IUserWriter] = None,
        jwt_secret: Optional[str] = None,
        **kwargs,
    ):
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self._local_db_service = DatabaseService(db_path=self.db_path) if self.db_path is not None else None
        self.jwt_secret = jwt_secret
        self.reader = reader or UserReader()
        self.writer = writer or UserWriter()

    @contextmanager
    def _connection(self):
        svc = self._local_db_service if self._local_db_service is not None else default_database_service
        with svc.get_connection() as conn:
            yield conn

    def format_user_response(self, user: dict) -> UserResponse:
        api_key = user.get("gemini_api_key") or user.get("api_key")
        preview = None
        if api_key:
            if len(api_key) > 8:
                preview = f"{api_key[:6]}...{api_key[-4:]}"
            else:
                preview = "******"

        return UserResponse(
            id=user["id"],
            email=user["email"],
            has_api_key=bool(api_key),
            api_key_preview=preview,
            created_at=user.get("created_at"),
            full_name=user.get("full_name"),
            role=user.get("role"),
        )

    def signup(
        self,
        req: Optional[UserSignupRequest] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        full_name: Optional[str] = None,
        role: Optional[str] = None,
        **kwargs,
    ) -> AuthResponse:
        if req is not None:
            email = req.email
            password = req.password
            full_name = getattr(req, "full_name", None) or full_name
            role = getattr(req, "role", None) or role

        email = (email or "").strip().lower()
        password = password or ""
        if not email or "@" not in email or "." not in email:
            raise ValueError("A valid email address is required")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")

        with logger.span("auth.signup", email=email):
            with self._connection() as conn:
                existing = self.reader.get_user_by_email(conn, email)
                if existing:
                    logger.warning("Signup rejected: user already exists", email=email)
                    raise ValueError("An account with this email address already exists")

                pwd_hash, salt = hash_password(password)
                user_id = self.writer.create_user(
                    conn,
                    email=email,
                    password_hash=pwd_hash,
                    salt=salt,
                    full_name=full_name,
                    role=role,
                )
                if conn is not None:
                    conn.commit()

                user = self.reader.get_user_by_id(conn, user_id)
                if not user:
                    raise ValueError("Failed to retrieve created user")

                token = create_access_token(user["id"], user["email"])
                logger.info("User registered successfully", user_id=user_id, email=email)
                return AuthResponse(token=token, user=self.format_user_response(user))

    def signin(
        self,
        req: Optional[UserSigninRequest] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs,
    ) -> AuthResponse:
        if req is not None:
            email = req.email
            password = req.password

        email = (email or "").strip().lower()
        password = password or ""

        with logger.span("auth.signin", email=email):
            with self._connection() as conn:
                user = self.reader.get_user_by_email(conn, email)
                if not user or not verify_password(password, user.get("salt", ""), user.get("password_hash", "")):
                    logger.warning("Signin failed: invalid credentials", email=email)
                    raise PermissionError("Invalid email or password")

                token = create_access_token(user["id"], user["email"])
                logger.info("User authenticated successfully", user_id=user["id"], email=email)
                return AuthResponse(token=token, user=self.format_user_response(user))

    def verify_token(self, token: str) -> Optional[dict]:
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            return None
        return {"id": payload["sub"], "email": payload.get("email", ""), "sub": payload["sub"]}

    def get_user_by_id(self, user_id: Any) -> Optional[dict]:
        with self._connection() as conn:
            return self.reader.get_user_by_id(conn, user_id)

    def get_user_by_email(self, email: str) -> Optional[dict]:
        with self._connection() as conn:
            return self.reader.get_user_by_email(conn, email)

    def create_api_key(self, user_id: Any) -> str:
        key = f"sk-{secrets.token_hex(16)}"
        with self._connection() as conn:
            self.writer.update_api_key(conn, user_id, key)
            if conn is not None:
                conn.commit()
        return key

    def verify_api_key(self, api_key: str) -> Optional[dict]:
        with self._connection() as conn:
            return self.reader.get_user_by_api_key(conn, api_key)

    def list_api_keys(self, user_id: Any) -> list:
        with self._connection() as conn:
            u = self.reader.get_user_by_id(conn, user_id)
            if u and (u.get("gemini_api_key") or u.get("api_key")):
                k = u.get("gemini_api_key") or u.get("api_key")
                return [{"api_key": k, "created_at": u.get("created_at")}]
            return []

    def revoke_api_key(self, user_id: Any, api_key: Optional[str] = None) -> bool:
        with self._connection() as conn:
            self.writer.delete_api_key(conn, user_id, api_key)
            if conn is not None:
                conn.commit()
            return True

    def get_user_from_token(self, token: str) -> Optional[dict]:
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            return None
        user_id = payload["sub"]

        with self._connection() as conn:
            return self.reader.get_user_by_id(conn, user_id)

    def set_user_api_key(self, user_id: Any, api_key: str) -> UserResponse:
        clean_key = api_key.strip()
        if not clean_key:
            raise ValueError("API key cannot be empty")

        with logger.span("auth.set_api_key", user_id=str(user_id)):
            with self._connection() as conn:
                self.writer.update_user_api_key(conn, user_id, clean_key)
                if conn is not None:
                    conn.commit()
                updated = self.reader.get_user_by_id(conn, user_id)
                if not updated:
                    raise LookupError("User not found")
                logger.info("User API key configured", user_id=str(user_id))
                return self.format_user_response(updated)

    def delete_user_api_key(self, user_id: Any) -> UserResponse:
        with logger.span("auth.delete_api_key", user_id=str(user_id)):
            with self._connection() as conn:
                self.writer.update_user_api_key(conn, user_id, None)
                if conn is not None:
                    conn.commit()
                updated = self.reader.get_user_by_id(conn, user_id)
                if not updated:
                    raise LookupError("User not found")
                logger.info("User API key cleared", user_id=str(user_id))
                return self.format_user_response(updated)


default_auth_service = AuthService()
