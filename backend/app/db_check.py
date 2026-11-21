"""Database connectivity check.

Usage (from ``backend/``):           python -m app.db_check
Inside the Compose API container:    docker compose exec api python -m app.db_check

Prints the redacted URL, server version, and applied Alembic revision.
Exit code 0 when the database is reachable, 1 otherwise.
"""

import sys
from dataclasses import dataclass

from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings

EXIT_OK = 0
EXIT_UNREACHABLE = 1
NOT_MIGRATED = "<none: run 'alembic upgrade head'>"


@dataclass(frozen=True)
class DatabaseInfo:
    dialect: str
    server_version: str
    alembic_revision: str | None


def check_database(engine: Engine) -> DatabaseInfo:
    """Connect, run ``SELECT 1``, and report server details. Raises SQLAlchemyError."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        version_info = conn.dialect.server_version_info or ()
        revision = MigrationContext.configure(conn).get_current_revision()
        return DatabaseInfo(
            dialect=conn.dialect.name,
            server_version=".".join(str(part) for part in version_info),
            alembic_revision=revision,
        )


def main() -> int:
    from app.core.database import engine

    settings = get_settings()
    print(f"Database URL : {settings.database_url_redacted}")
    try:
        info = check_database(engine)
    except SQLAlchemyError as exc:
        print(f"Status       : UNREACHABLE ({type(exc).__name__})", file=sys.stderr)
        return EXIT_UNREACHABLE
    print("Status       : OK")
    print(f"Dialect      : {info.dialect} {info.server_version}")
    print(f"Revision     : {info.alembic_revision or NOT_MIGRATED}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
