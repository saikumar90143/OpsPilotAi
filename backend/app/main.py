"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.incidents import router as incidents_router
from app.core.config import APP_NAME, FRONTEND_ORIGIN
from app.core.database import Base, engine
from app.models import Incident  # noqa: F401 - ensure model metadata is registered


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create starter tables at startup.

    We will replace create_all with Alembic migrations in the database milestone.
    """
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=APP_NAME,
    description="An enterprise incident investigation and workflow automation platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Basic process health check (database health is added in a later milestone)."""
    return {"status": "ok", "service": "opspilot-api"}


app.include_router(incidents_router)
