from pathlib import Path
from typing import Optional, Dict, Any

from contextlib import contextmanager
from src.services.database import get_db_connection, is_deployed
from src.services.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from src.services.auth.types import (
    IAuthService,
    IUserReader,
    IUserWriter,
    UserSignupRequest,
    UserSigninRequest,
    UserResponse,
    AuthResponse,
)
from src.services.auth.repositories.reader import UserReader
from src.services.auth.repositories.writer import UserWriter
from src.services.auth.repositories.dynamo_user import DynamoUserRepository
from src.services.logger import get_logger

logger = get_logger("services.auth")


class AuthService(IAuthService):
    def __init__(
        self,
        db_path: Optional[Path] = None,
        reader: Optional[IUserReader] = None,
        writer: Optional[IUserWriter] = None,
    ):
        self.db_path = db_path
        if is_deployed() and (reader is None or writer is None):
            dynamo_repo = DynamoUserRepository()
            self.reader = reader or dynamo_repo
            self.writer = writer or dynamo_repo
        else:
            self.reader = reader or UserReader()
            self.writer = writer or UserWriter()

    @contextmanager
    def _connection(self):
        if isinstance(self.reader, DynamoUserRepository):
            yield None
        else:
            with get_db_connection(self.db_path) as conn:
                yield conn

    def format_user_response(self, user: dict) -> UserResponse:
        api_key = user.get("gemini_api_key")
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
        )

    def signup(self, req: UserSignupRequest) -> AuthResponse:
        email = req.email.strip().lower()
        if not email or "@" not in email or "." not in email:
            raise ValueError("A valid email address is required")
        if len(req.password) < 6:
            raise ValueError("Password must be at least 6 characters long")

        with logger.span("auth.signup", email=email):
            with self._connection() as conn:
                existing = self.reader.get_user_by_email(conn, email)
                if existing:
                    logger.warning("Signup rejected: user already exists", email=email)
                    raise ValueError("An account with this email address already exists")

                pwd_hash, salt = hash_password(req.password)
                user_id = self.writer.create_user(conn, email, pwd_hash, salt)
                if conn is not None:
                    conn.commit()

                user = self.reader.get_user_by_id(conn, user_id)
                if not user:
                    raise ValueError("Failed to retrieve created user")

                token = create_access_token(user["id"], user["email"])
                logger.info("User registered successfully", user_id=user_id, email=email)
                return AuthResponse(token=token, user=self.format_user_response(user))

    def signin(self, req: UserSigninRequest) -> AuthResponse:
        email = req.email.strip().lower()
        with logger.span("auth.signin", email=email):
            with self._connection() as conn:
                user = self.reader.get_user_by_email(conn, email)
                if not user or not verify_password(req.password, user["salt"], user["password_hash"]):
                    logger.warning("Signin failed: invalid credentials", email=email)
                    raise PermissionError("Invalid email or password")

                token = create_access_token(user["id"], user["email"])
                logger.info("User authenticated successfully", user_id=user["id"], email=email)
                return AuthResponse(token=token, user=self.format_user_response(user))

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
