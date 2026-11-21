"""Request context middleware: correlation IDs, access logging, 500 boundary."""

import logging
import re
import time
import uuid
from http import HTTPStatus

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import INTERNAL_ERROR_MESSAGE, error_response
from app.core.errors import ErrorCode
from app.core.logging import REQUEST_ID_HEADER, request_id_var
from app.core.telemetry import (
    HTTP_ERRORS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)

logger = logging.getLogger("app.request")

MAX_REQUEST_ID_LENGTH = 128
_VALID_REQUEST_ID = re.compile(rf"^[A-Za-z0-9._\-]{{1,{MAX_REQUEST_ID_LENGTH}}}$")


def resolve_request_id(inbound: str | None) -> str:
    """Accept a well-formed inbound ID (safe for logs/headers); otherwise generate one."""
    if inbound and _VALID_REQUEST_ID.fullmatch(inbound):
        return inbound
    return uuid.uuid4().hex


class RequestContextMiddleware:
    """Pure ASGI middleware (keeps contextvars intact through the whole request)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = resolve_request_id(Headers(scope=scope).get(REQUEST_ID_HEADER))
        token = request_id_var.set(request_id)
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR.value
        response_started = False
        started_at = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                if scope.get("path", "").startswith("/api/"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            # Boundary: log full context once, return a safe generic body.
            logger.exception("Unhandled exception while processing request")
            if response_started:
                raise
            response = error_response(
                HTTPStatus.INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR, INTERNAL_ERROR_MESSAGE
            )
            await response(scope, receive, send_with_request_id)
        finally:
            elapsed_s = time.perf_counter() - started_at
            duration_ms = round(elapsed_s * 1000, 2)
            method, path = scope["method"], scope["path"]
            route_obj = scope.get("route")
            route_label = getattr(route_obj, "path", None) or "unmatched"
            status_class = f"{status_code // 100}xx"
            if route_label != "/metrics":
                HTTP_REQUESTS_TOTAL.labels(
                    method=method, route=route_label, status_class=status_class
                ).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(method=method, route=route_label).observe(
                    elapsed_s
                )
                if status_code >= 400:
                    HTTP_ERRORS_TOTAL.labels(
                        method=method, route=route_label, status_class=status_class
                    ).inc()
            logger.info(
                "%s %s -> %s (%.2f ms)",
                method,
                path,
                status_code,
                duration_ms,
                extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            request_id_var.reset(token)
