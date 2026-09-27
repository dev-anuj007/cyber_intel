from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class UserSignupRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "member"


class UserSigninRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str
    password: str


class SignupCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "member"


class SigninCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    email: str
    has_api_key: bool = False
    api_key_preview: Optional[str] = None
    created_at: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None


class AuthResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: str
    user: UserResponse


class ApiKeyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    api_key: Optional[str] = None


class UpdateApiKeyCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: int
    api_key: Optional[str] = None


class ApiKeyItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    api_key: str
    created_at: Optional[str] = None


class ApiKeyListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class ApiKeyOperationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool = True
    message: str
    api_key: Optional[str] = None
    user_id: Optional[int] = None
