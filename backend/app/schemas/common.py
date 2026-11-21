"""Shared API schemas: error envelope and health probes."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Consistent body for every non-2xx API response."""

    error: str = Field(description="Machine-readable error code.", examples=["not_found"])
    message: str = Field(description="Human-readable description.")
    request_id: str = Field(description="Correlation ID; matches the X-Request-ID header.")
    details: list[dict[str, Any]] | None = Field(
        default=None, description="Field-level validation errors (validation_error only)."
    )


class CheckStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckStatus]
