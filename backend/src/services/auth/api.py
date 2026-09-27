from typing import Optional

from fastapi import APIRouter, Depends

from src.core.exceptions import (
    AuthenticationError,
    ConflictError,
    ExternalServiceError,
    InvalidInputError,
    NotFoundError,
)
from src.services.auth.dependencies import (
    get_auth_service,
    get_current_user,
)
from src.services.auth.protocols import IAuthService
from src.services.auth.types import (
    ApiKeyUpdateRequest,
    AuthResponse,
    UserResponse,
    UserSigninRequest,
    UserSignupRequest,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/health")
def auth_health():
    return {"status": "healthy", "service": "auth"}


@router.post("/signup", response_model=AuthResponse)
def signup(
    req: UserSignupRequest,
    auth_service: IAuthService = Depends(get_auth_service),
):
    try:
        return auth_service.signup(req)
    except ValueError as e:
        err_msg = str(e)
        if "already exists" in err_msg.lower():
            raise ConflictError(message=err_msg, code="USER_ALREADY_EXISTS")
        raise InvalidInputError(message=err_msg, code="INVALID_SIGNUP_INPUT")
    except Exception as e:
        raise ExternalServiceError(message=f"Registration failed: {str(e)}", code="REGISTRATION_FAILED")


@router.post("/signin", response_model=AuthResponse)
def signin(
    req: UserSigninRequest,
    auth_service: IAuthService = Depends(get_auth_service),
):
    try:
        return auth_service.signin(req)
    except PermissionError as e:
        raise AuthenticationError(message=str(e), code="INVALID_CREDENTIALS")
    except Exception as e:
        raise ExternalServiceError(message=f"Authentication failed: {str(e)}", code="AUTHENTICATION_FAILED")


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    auth_service: IAuthService = Depends(get_auth_service),
):
    return auth_service.format_user_response(current_user)


@router.post("/api-key")
def create_or_set_user_api_key(
    req: Optional[ApiKeyUpdateRequest] = None,
    current_user: dict = Depends(get_current_user),
    auth_service: IAuthService = Depends(get_auth_service),
):
    try:
        if req and req.api_key:
            auth_service.set_user_api_key(current_user["id"], req.api_key)
            return {"api_key": req.api_key, "user_id": current_user["id"], "success": True}
        else:
            api_key = auth_service.create_api_key(current_user["id"])
            return {"api_key": api_key, "user_id": current_user["id"], "success": True}
    except ValueError as e:
        raise InvalidInputError(message=str(e), code="INVALID_API_KEY")
    except LookupError as e:
        raise NotFoundError(message=str(e), code="USER_NOT_FOUND")
    except Exception as e:
        raise ExternalServiceError(message=f"Failed to process API key: {str(e)}", code="API_KEY_FAILED")


@router.get("/api-key/list")
def list_user_api_keys(
    current_user: dict = Depends(get_current_user),
    auth_service: IAuthService = Depends(get_auth_service),
):
    keys = auth_service.list_api_keys(current_user["id"])
    return {"items": keys, "total": len(keys)}


@router.post("/api-key/revoke")
def revoke_user_api_key(
    req: Optional[dict] = None,
    current_user: dict = Depends(get_current_user),
    auth_service: IAuthService = Depends(get_auth_service),
):
    key = req.get("api_key") if isinstance(req, dict) else None
    auth_service.revoke_api_key(current_user["id"], key)
    return {"success": True, "message": "API key revoked"}


@router.delete("/api-key", response_model=UserResponse)
def delete_user_api_key(
    current_user: dict = Depends(get_current_user),
    auth_service: IAuthService = Depends(get_auth_service),
):
    try:
        return auth_service.delete_user_api_key(current_user["id"])
    except LookupError as e:
        raise NotFoundError(message=str(e), code="USER_NOT_FOUND")
    except Exception as e:
        raise ExternalServiceError(message=f"Failed to remove API key: {str(e)}", code="API_KEY_DELETE_FAILED")
