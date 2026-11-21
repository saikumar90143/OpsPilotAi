"""Typed, environment-backed application settings.

Values are read (highest priority first) from process environment variables, the
repository-root ``.env`` file, then ``backend/.env``. Missing files are ignored.
Only ``.env.example`` (placeholders) is committed; ``.env`` is git-ignored.
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT_ENV_FILE = BACKEND_DIR.parent / ".env"
BACKEND_ENV_FILE = BACKEND_DIR / ".env"

DEFAULT_DATABASE_URL = "sqlite:///./opspilot.db"
SQLITE_DRIVER = "sqlite"
POSTGRES_DRIVER = "postgresql+psycopg"
SUPPORTED_DATABASE_DRIVERS = frozenset({SQLITE_DRIVER, POSTGRES_DRIVER})
INVALID_URL_PLACEHOLDER = "<invalid database url>"

DEV_ONLY_JWT_SECRET = "dev-only-insecure-secret-change-before-production-32b"
MIN_JWT_SECRET_LENGTH = 32

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    CONSOLE = "console"
    JSON = "json"


def redact_url(url: str) -> str:
    """Return the URL with any password masked; never raises."""
    try:
        return make_url(url).render_as_string(hide_password=True)
    except ArgumentError:
        return INVALID_URL_PLACEHOLDER


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ENV_FILE, REPO_ROOT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        # Never echo raw input (e.g. a DATABASE_URL or JWT_SECRET_KEY) in validation errors.
        hide_input_in_errors=True,
    )

    app_name: str = "OpsPilot AI API"
    app_env: AppEnv = AppEnv.DEVELOPMENT
    database_url: str = Field(default=DEFAULT_DATABASE_URL, repr=False)
    frontend_origin: str = "http://localhost:3000"
    log_level: LogLevel = "INFO"
    log_format: LogFormat | None = None
    db_connect_timeout_seconds: int = Field(default=3, ge=1, le=60)

    # Phase 2: Authentication & sessions
    jwt_secret_key: str = Field(default=DEV_ONLY_JWT_SECRET, repr=False)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)
    invitation_expire_hours: int = Field(default=72, ge=1, le=720)
    cookie_secure: bool | None = None
    auth_rate_limit_requests: int = Field(default=10, ge=1, le=1000)
    auth_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)

    # Phase 4: Event ingestion & queue
    redis_url: str = Field(default="redis://localhost:6379/0", repr=False)
    integration_encryption_key: str | None = Field(default=None, repr=False)
    webhook_max_bytes: int = Field(default=262_144, ge=1024, le=5_242_880)
    webhook_signature_tolerance_seconds: int = Field(default=300, ge=30, le=3600)
    webhook_rate_limit_requests: int = Field(default=60, ge=1, le=10_000)
    webhook_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    event_max_attempts: int = Field(default=3, ge=1, le=10)
    secret_rotation_grace_hours: int = Field(default=24, ge=1, le=168)

    # Phase 6: Read-only GitHub connector
    github_api_base_url: str = "https://api.github.com"
    github_request_timeout_seconds: int = Field(default=10, ge=1, le=60)
    github_correlation_lookback_hours: int = Field(default=24, ge=1, le=168)

    # Phase 7: Evidence layer (logs & engineering knowledge base)
    log_query_default_window_hours: int = Field(default=24, ge=1, le=168)
    log_query_max_window_hours: int = Field(default=168, ge=1, le=720)
    log_ingest_max_batch: int = Field(default=100, ge=1, le=500)
    kb_max_upload_bytes: int = Field(default=524_288, ge=1024, le=5_242_880)
    kb_chunk_size_chars: int = Field(default=800, ge=200, le=4000)
    kb_chunk_overlap_chars: int = Field(default=120, ge=0, le=500)
    kb_index_max_attempts: int = Field(default=3, ge=1, le=10)

    # Phase 8: Read-only AI investigation copilot
    ai_provider_mode: Literal["mock", "openai"] = "mock"
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_model: str = "gpt-4.1-mini"
    ai_prompt_version: str = "v1.0-readonly-copilot"
    ai_max_graph_steps: int = Field(default=8, ge=4, le=20)
    ai_max_tool_calls: int = Field(default=6, ge=1, le=12)
    ai_tool_timeout_seconds: float = Field(default=5.0, ge=0.5, le=30.0)
    ai_model_timeout_seconds: float = Field(default=20.0, ge=1.0, le=120.0)
    ai_max_input_tokens: int = Field(default=12_000, ge=1000, le=100_000)
    ai_max_output_tokens: int = Field(default=2000, ge=256, le=8000)
    ai_rate_limit_requests: int = Field(default=10, ge=1, le=1000)
    ai_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    ai_tenant_daily_quota: int = Field(default=50, ge=1, le=10_000)

    # Phase 9: Controlled external write actions (human approval gate)
    action_allow_self_approval: bool = False
    action_default_ttl_hours: int = Field(default=24, ge=1, le=168)
    action_max_execution_retries: int = Field(default=2, ge=0, le=5)
    action_request_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)

    # Phase 10: Observability, metrics & AI evaluation
    otel_enabled: bool = True
    otel_service_name: str = "opspilot-api"
    metrics_enabled: bool = True
    langfuse_enabled: bool = False

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        try:
            driver = make_url(value).drivername
        except ArgumentError as exc:
            raise ValueError("DATABASE_URL is not a valid SQLAlchemy URL") from exc
        if driver not in SUPPORTED_DATABASE_DRIVERS:
            raise ValueError(
                f"Unsupported DATABASE_URL driver '{driver}'. Use '{POSTGRES_DRIVER}://...' "
                f"(primary) or '{SQLITE_DRIVER}:///...' (local/tests)."
            )
        return value

    @model_validator(mode="after")
    def _validate_production_settings(self) -> "Settings":
        if self.app_env is AppEnv.PRODUCTION and self.is_sqlite:
            raise ValueError("SQLite is not supported when APP_ENV=production; use PostgreSQL.")
        if self.app_env is AppEnv.PRODUCTION and (
            self.jwt_secret_key == DEV_ONLY_JWT_SECRET
            or len(self.jwt_secret_key) < MIN_JWT_SECRET_LENGTH
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be an explicit secret of at least 32 characters "
                "when APP_ENV=production."
            )
        if self.app_env is AppEnv.PRODUCTION and not self.integration_encryption_key:
            raise ValueError(
                "INTEGRATION_ENCRYPTION_KEY must be set explicitly when APP_ENV=production."
            )
        return self

    @property
    def is_sqlite(self) -> bool:
        return make_url(self.database_url).get_backend_name() == SQLITE_DRIVER

    @property
    def database_url_redacted(self) -> str:
        return redact_url(self.database_url)

    @property
    def effective_log_format(self) -> LogFormat:
        if self.log_format is not None:
            return self.log_format
        return LogFormat.JSON if self.app_env is AppEnv.PRODUCTION else LogFormat.CONSOLE

    @property
    def effective_cookie_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env is AppEnv.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached)."""
    return Settings()
