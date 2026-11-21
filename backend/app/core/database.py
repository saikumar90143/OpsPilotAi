"""SQLAlchemy engine, session factory, and request-scoped session lifecycle.

PostgreSQL is the primary supported database. SQLite remains available for
zero-configuration local runs and fast tests.

Transaction boundary: ``get_db`` provides one session per request and rolls
back on any exception. Service functions commit explicitly at the end of each
write use case; nothing is committed implicitly.
"""

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import SQLITE_DRIVER, Settings, get_settings

# Deterministic constraint/index names so Alembic migrations are reproducible.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def build_engine(settings: Settings) -> Engine:
    """Create an engine with driver-appropriate connection arguments."""
    url = make_url(settings.database_url)
    connect_args: dict[str, Any]
    if url.get_backend_name() == SQLITE_DRIVER:
        connect_args = {"check_same_thread": False}
    else:
        # Bounded connect time so readiness checks fail fast instead of hanging.
        connect_args = {"connect_timeout": settings.db_connect_timeout_seconds}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


engine = build_engine(get_settings())
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db() -> Iterator[Session]:
    """Yield one session per request; roll back on error and always close."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
