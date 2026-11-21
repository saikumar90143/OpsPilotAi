"""Authentication endpoints: login, refresh, logout, accept-invite, and current user."""

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    AppSettings,
    CurrentAuth,
    DbSession,
    enforce_auth_rate_limit,
    get_client_ip,
    verify_csrf,
)
from app.api.errors import ERROR_RESPONSES
from app.core.config import Settings
from app.schemas.auth import (
    AcceptInviteRequest,
    AuthSessionRead,
    LoginRequest,
    OrganizationRead,
    UserRead,
)
from app.services import auth_service
from app.services.auth_service import IssuedSession

AUTH_PREFIX = "/api/v1/auth"
SECONDS_PER_MINUTE = 60
SECONDS_PER_DAY = 86_400

router = APIRouter(prefix="/auth", tags=["auth"], responses=ERROR_RESPONSES)


def _set_auth_cookies(response: Response, issued: IssuedSession, settings: Settings) -> None:
    secure = settings.effective_cookie_secure
    access_max_age = settings.access_token_expire_minutes * SECONDS_PER_MINUTE
    refresh_max_age = settings.refresh_token_expire_days * SECONDS_PER_DAY

    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=issued.access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=access_max_age,
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=issued.refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        # Scoped to auth endpoints so the refresh token is not sent on regular API calls.
        path=AUTH_PREFIX,
        max_age=refresh_max_age,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=issued.csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=refresh_max_age,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=AUTH_PREFIX)
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")


def _session_body(issued: IssuedSession) -> AuthSessionRead:
    ctx = issued.context
    return AuthSessionRead(
        user=UserRead.model_validate(ctx.user),
        organization=OrganizationRead.model_validate(ctx.organization),
        role=ctx.role,
    )


@router.post(
    "/login",
    response_model=AuthSessionRead,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> AuthSessionRead:
    """Authenticate with email + password and issue HttpOnly session cookies."""
    issued = auth_service.authenticate_user(
        db,
        email=payload.email,
        password=payload.password,
        organization_slug=payload.organization_slug,
        settings=settings,
        ip_address=get_client_ip(request),
    )
    _set_auth_cookies(response, issued, settings)
    return _session_body(issued)


@router.post(
    "/refresh",
    response_model=AuthSessionRead,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> AuthSessionRead:
    """Rotate the refresh token and issue a fresh short-lived access token."""
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        verify_csrf(request)
    issued = auth_service.refresh_session(
        db,
        raw_refresh_token=raw_refresh,
        settings=settings,
        ip_address=get_client_ip(request),
    )
    _set_auth_cookies(response, issued, settings)
    return _session_body(issued)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession) -> None:
    """Revoke the active refresh token family and clear session cookies."""
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh or request.cookies.get(ACCESS_COOKIE_NAME):
        verify_csrf(request)
    auth_service.logout_session(
        db,
        raw_refresh_token=raw_refresh,
        ip_address=get_client_ip(request),
    )
    _clear_auth_cookies(response)


@router.post(
    "/accept-invite",
    response_model=AuthSessionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
def accept_invite(
    payload: AcceptInviteRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> AuthSessionRead:
    """Accept an organization invitation and start an authenticated session."""
    issued = auth_service.accept_invitation(
        db,
        raw_token=payload.token,
        full_name=payload.full_name,
        password=payload.password,
        settings=settings,
        ip_address=get_client_ip(request),
    )
    _set_auth_cookies(response, issued, settings)
    return _session_body(issued)


@router.get("/me", response_model=AuthSessionRead)
def current_user(auth: CurrentAuth) -> AuthSessionRead:
    """Return the authenticated user, active organization, and verified DB role."""
    return AuthSessionRead(
        user=UserRead.model_validate(auth.user),
        organization=OrganizationRead.model_validate(auth.organization),
        role=auth.role,
    )
