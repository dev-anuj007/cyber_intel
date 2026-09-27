from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class UserSignupRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    email: str
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "member"


class UserSigninRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    email: str
    password: str


class SignupCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    email: str
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "member"


class SigninCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Any
    email: str
    has_api_key: bool = False
    api_key_preview: Optional[str] = None
    created_at: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) and getattr(self, item) is not None

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def keys(self) -> list:
        return ["id", "email", "has_api_key", "api_key_preview", "created_at", "full_name", "role"]


class AuthResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    token: str
    user: UserResponse

    def __getitem__(self, item: str) -> Any:
        if item == "token":
            return self.token
        if item == "user":
            return self.user
        if hasattr(self.user, item):
            return getattr(self.user, item)
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return item in ("token", "user") or (hasattr(self.user, item) and getattr(self.user, item) is not None)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def keys(self) -> list:
        return ["token", "user"]


class ApiKeyUpdateRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    api_key: Optional[str] = None


class UpdateApiKeyCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_id: Any
    api_key: Optional[str] = None



