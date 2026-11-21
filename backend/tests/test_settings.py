"""Settings validation and secret handling."""

import pytest
from pydantic import ValidationError

from app.core.config import AppEnv, LogFormat, Settings, redact_url

PG_URL = "postgresql+psycopg://opspilot:s3cr3t-value@db.internal:5432/opspilot"
SECRET = "s3cr3t-value"


def make(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[call-arg]


def test_defaults(monkeypatch: pytest.MonkeyPatch):
    for var in ("APP_ENV", "DATABASE_URL", "LOG_LEVEL", "LOG_FORMAT"):
        monkeypatch.delenv(var, raising=False)
    settings = make()
    assert settings.app_env is AppEnv.DEVELOPMENT
    assert settings.database_url == "sqlite:///./opspilot.db"
    assert settings.log_level == "INFO"
    assert settings.effective_log_format is LogFormat.CONSOLE


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", PG_URL)
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("INTEGRATION_ENCRYPTION_KEY", "test-fernet-key-placeholder-32-bytes==")
    settings = make()
    assert settings.app_env is AppEnv.PRODUCTION
    assert settings.database_url == PG_URL
    assert settings.log_level == "WARNING"
    assert settings.effective_log_format is LogFormat.JSON


@pytest.mark.parametrize(
    ("field", "value"),
    [("app_env", "staging"), ("log_level", "VERBOSE"), ("log_format", "xml")],
)
def test_rejects_invalid_enum_values(field: str, value: str):
    with pytest.raises(ValidationError):
        make(**{field: value})


@pytest.mark.parametrize("timeout", [0, 61])
def test_rejects_out_of_range_connect_timeout(timeout: int):
    with pytest.raises(ValidationError):
        make(db_connect_timeout_seconds=timeout)


@pytest.mark.parametrize(
    "url",
    [
        "mysql://user:s3cr3t-value@host/db",
        "postgresql://user:s3cr3t-value@host/db",  # psycopg2 driver is not installed
        "not a url",
    ],
)
def test_rejects_unsupported_database_urls_without_leaking_secret(url: str):
    with pytest.raises(ValidationError) as excinfo:
        make(database_url=url)
    assert SECRET not in str(excinfo.value)


def test_production_rejects_sqlite():
    with pytest.raises(ValidationError, match="SQLite is not supported"):
        make(app_env="production", database_url="sqlite:///./x.db")


def test_production_accepts_postgres():
    settings = make(
        app_env="production",
        database_url=PG_URL,
        jwt_secret_key="a-real-production-jwt-secret-of-32-plus-bytes",
        integration_encryption_key="test-fernet-key-placeholder-32-bytes==",
    )
    assert settings.is_sqlite is False
    assert settings.effective_cookie_secure is True


def test_production_rejects_default_or_short_jwt_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        make(
            app_env="production",
            database_url=PG_URL,
            integration_encryption_key="test-fernet-key-placeholder-32-bytes==",
        )
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        make(
            app_env="production",
            database_url=PG_URL,
            jwt_secret_key="too-short",
            integration_encryption_key="test-fernet-key-placeholder-32-bytes==",
        )


def test_production_rejects_missing_integration_encryption_key():
    with pytest.raises(ValidationError, match="INTEGRATION_ENCRYPTION_KEY"):
        make(
            app_env="production",
            database_url=PG_URL,
            jwt_secret_key="a-real-production-jwt-secret-of-32-plus-bytes",
        )


def test_repr_and_redacted_url_never_contain_password():
    settings = make(database_url=PG_URL, jwt_secret_key="super-secret-jwt-key-32-bytes-long!!")
    assert SECRET not in repr(settings)
    assert "super-secret-jwt-key" not in repr(settings)
    assert SECRET not in str(settings)
    assert SECRET not in settings.database_url_redacted
    assert "***" in settings.database_url_redacted


def test_redact_url_handles_invalid_input():
    assert redact_url("not a url") == "<invalid database url>"
    assert redact_url("sqlite:///./opspilot.db") == "sqlite:///./opspilot.db"
