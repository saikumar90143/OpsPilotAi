"""FastAPI dependencies: authentication, CSRF verification, RBAC, and rate limiting."""

import hmac
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.permissions import Permission, has_permission
from app.core.rate_limit import auth_rate_limiter
from app.services import auth_service
from app.services.auth_service import AuthContext

ACCESS_COOKIE_NAME = "opspilot_access"
REFRESH_COOKIE_NAME = "opspilot_refresh"
CSRF_COOKIE_NAME = "opspilot_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
BEARER_PREFIX = "Bearer "
STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def verify_csrf(request: Request) -> None:
    """Double-submit CSRF check for cookie-authenticated state-changing requests."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise ForbiddenError("CSRF validation failed")


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith(BEARER_PREFIX):
        return auth_header.removeprefix(BEARER_PREFIX).strip() or None
    return None


def get_auth_context(request: Request, db: DbSession, settings: AppSettings) -> AuthContext:
    bearer = _extract_bearer_token(request)
    if bearer is not None:
        return auth_service.resolve_auth_context(db, access_token=bearer, settings=settings)

    cookie_token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not cookie_token:
        raise UnauthorizedError("Authentication required")

    if request.method in STATE_CHANGING_METHODS:
        verify_csrf(request)

    return auth_service.resolve_auth_context(db, access_token=cookie_token, settings=settings)


CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


def require_permission(permission: Permission) -> Callable[[AuthContext], AuthContext]:
    def _dependency(auth: CurrentAuth) -> AuthContext:
        if not has_permission(auth.role, permission):
            raise ForbiddenError("Insufficient permissions for this action")
        return auth

    return _dependency


def enforce_auth_rate_limit(request: Request, settings: AppSettings) -> None:
    client_ip = get_client_ip(request) or "unknown"
    key = f"{request.url.path}:{client_ip}"
    auth_rate_limiter.check(
        key,
        max_requests=settings.auth_rate_limit_requests,
        window_seconds=settings.auth_rate_limit_window_seconds,
    )
