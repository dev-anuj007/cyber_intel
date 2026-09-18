from typing import Any, Optional


class AppException(Exception):
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND", details: Optional[Any] = None):
        super().__init__(message=message, code=code, status_code=404, details=details)


class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication required", code: str = "UNAUTHENTICATED", details: Optional[Any] = None):
        super().__init__(message=message, code=code, status_code=401, details=details)


class AuthorizationError(AppException):
    def __init__(self, message: str = "Permission denied", code: str = "PERMISSION_DENIED", details: Optional[Any] = None):
        super().__init__(message=message, code=code, status_code=403, details=details)


class InvalidInputError(AppException):
    def __init__(self, message: str = "Invalid input provided", code: str = "INVALID_INPUT", details: Optional[Any] = None):
        super().__init__(message=message, code=code, status_code=400, details=details)


class ConflictError(AppException):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT", details: Optional[Any] = None):
        super().__init__(message=message, code=code, status_code=409, details=details)


class RateLimitError(AppException):
    def __init__(self, message: str = "Rate limit exceeded", code: str = "RATE_LIMIT_EXCEEDED", details: Optional[Any] = None):
        super().__init__(message=message, code=code, status_code=429, details=details)


class ExternalServiceError(AppException):
    def __init__(self, message: str = "External service failure", code: str = "EXTERNAL_SERVICE_ERROR", status_code: int = 502, details: Optional[Any] = None):
        super().__init__(message=message, code=code, status_code=status_code, details=details)


class DatabaseError(AppException):
    def __init__(self, message: str = "Database operation failed", code: str = "DATABASE_ERROR", details: Optional[Any] = None):
        super().__init__(message=message, code=code, status_code=500, details=details)
