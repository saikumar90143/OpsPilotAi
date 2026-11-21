"""Transport-agnostic domain errors.

Services raise these; the API layer maps them to HTTP responses.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    CONFLICT = "conflict"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    VALIDATION_ERROR = "validation_error"
    RATE_LIMITED = "rate_limited"
    SERVICE_UNAVAILABLE = "service_unavailable"
    HTTP_ERROR = "http_error"
    INTERNAL_ERROR = "internal_error"


class AppError(Exception):
    """Base class for expected, client-facing domain errors."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnauthorizedError(AppError):
    code = ErrorCode.UNAUTHORIZED


class ForbiddenError(AppError):
    code = ErrorCode.FORBIDDEN


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND


class ConflictError(AppError):
    code = ErrorCode.CONFLICT


class RateLimitedError(AppError):
    code = ErrorCode.RATE_LIMITED


class PayloadTooLargeError(AppError):
    code = ErrorCode.PAYLOAD_TOO_LARGE


class ValidationError(AppError):
    code = ErrorCode.VALIDATION_ERROR


class ServiceUnavailableError(AppError):
    code = ErrorCode.SERVICE_UNAVAILABLE
