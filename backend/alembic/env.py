"""Alembic environment: the authoritative schema-management entry point."""

import logging

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (register all models on Base.metadata)
from app.core.config import get_settings, redact_url
from app.core.database import Base

config = context.config
target_metadata = Base.metadata
logger = logging.getLogger("alembic.env")

# Only configure logging when run from the CLI; never clobber an existing setup (e.g. pytest).
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-5s [%(name)s] %(message)s")


def _database_url() -> str:
    url = config.attributes.get("database_url")
    return str(url) if url else get_settings().database_url


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _database_url()
    logger.info("Migrating database %s", redact_url(url))
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                render_as_batch=connection.dialect.name == "sqlite",
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
