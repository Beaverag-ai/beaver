from __future__ import annotations

from typing import Any


class BeaverError(Exception):
    def __init__(
        self,
        message: str,
        error_type: str = "beaver_error",
        code: str | None = None,
        status_code: int = 500,
    ):
        self.message = message
        self.error_type = error_type
        self.code = code
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        error = {"message": self.message, "type": self.error_type}
        if self.code:
            error["code"] = self.code
        return {"error": error}


class AuthenticationError(BeaverError):
    def __init__(self, message: str = "Invalid or missing API key"):
        super().__init__(
            message=message,
            error_type="authentication_error",
            code="invalid_api_key",
            status_code=401,
        )


class AuthorizationError(BeaverError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            error_type="authorization_error",
            code="insufficient_scope",
            status_code=403,
        )


class NotFoundError(BeaverError):
    def __init__(self, resource: str, resource_id: str | None = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} '{resource_id}' not found"
        super().__init__(
            message=message,
            error_type="not_found_error",
            code="resource_not_found",
            status_code=404,
        )


class ValidationError(BeaverError):
    def __init__(self, message: str):
        super().__init__(
            message=message,
            error_type="validation_error",
            code="invalid_request",
            status_code=400,
        )


class RateLimitError(BeaverError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            error_type="rate_limit_error",
            code="rate_limit_exceeded",
            status_code=429,
        )


class ServiceUnavailableError(BeaverError):
    def __init__(self, service: str):
        super().__init__(
            message=f"{service} is currently unavailable",
            error_type="service_unavailable",
            code="service_unavailable",
            status_code=503,
        )
