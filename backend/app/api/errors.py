"""Map domain and framework exceptions to the consistent ``ErrorResponse`` shape."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ErrorCode
from app.core.logging import request_id_var
from app.schemas.common import ErrorResponse

VALIDATION_MESSAGE = "Request validation failed."
INTERNAL_ERROR_MESSAGE = "An unexpected error occurred."

_APP_ERROR_STATUS: dict[ErrorCode, int] = {
    ErrorCode.UNAUTHORIZED: HTTPStatus.UNAUTHORIZED,
    ErrorCode.FORBIDDEN: HTTPStatus.FORBIDDEN,
    ErrorCode.NOT_FOUND: HTTPStatus.NOT_FOUND,
    ErrorCode.CONFLICT: HTTPStatus.CONFLICT,
    ErrorCode.PAYLOAD_TOO_LARGE: HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
    ErrorCode.VALIDATION_ERROR: HTTPStatus.UNPROCESSABLE_ENTITY,
    ErrorCode.RATE_LIMITED: HTTPStatus.TOO_MANY_REQUESTS,
    ErrorCode.SERVICE_UNAVAILABLE: HTTPStatus.SERVICE_UNAVAILABLE,
}
_HTTP_STATUS_CODE: dict[int, ErrorCode] = {
    HTTPStatus.UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
    HTTPStatus.FORBIDDEN: ErrorCode.FORBIDDEN,
    HTTPStatus.NOT_FOUND: ErrorCode.NOT_FOUND,
    HTTPStatus.METHOD_NOT_ALLOWED: ErrorCode.METHOD_NOT_ALLOWED,
    HTTPStatus.CONFLICT: ErrorCode.CONFLICT,
    HTTPStatus.TOO_MANY_REQUESTS: ErrorCode.RATE_LIMITED,
}

# Reusable OpenAPI ``responses=`` entries.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse, "description": "Authentication required"},
    HTTPStatus.FORBIDDEN: {"model": ErrorResponse, "description": "Insufficient permissions"},
    HTTPStatus.NOT_FOUND: {"model": ErrorResponse, "description": "Resource not found"},
    HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse, "description": "Validation error"},
}


def error_response(
    status_code: int,
    code: ErrorCode,
    message: str,
    *,
    details: list[dict[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=code, message=message, request_id=request_id_var.get(), details=details
    )
    return JSONResponse(
        status_code=status_code, content=body.model_dump(exclude_none=True), headers=headers
    )


async def _handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    status_code = _APP_ERROR_STATUS.get(exc.code, HTTPStatus.INTERNAL_SERVER_ERROR)
    return error_response(status_code, exc.code, exc.message)


async def _handle_http_exception(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_STATUS_CODE.get(exc.status_code, ErrorCode.HTTP_ERROR)
    message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    return error_response(exc.status_code, code, message, headers=exc.headers)


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Deliberately omit the raw "input" so request values (e.g. passwords) are never echoed back.
    details = [
        {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in exc.errors()
    ]
    return error_response(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        ErrorCode.VALIDATION_ERROR,
        VALIDATION_MESSAGE,
        details=details,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
