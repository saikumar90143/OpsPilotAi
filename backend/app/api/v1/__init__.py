"""Version 1 of the public API. All v1 routers are mounted under ``/api/v1``."""

from fastapi import APIRouter

from app.api.v1.actions import router as actions_router
from app.api.v1.auth import router as auth_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.github import router as github_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.investigations import router as investigations_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.webhooks import router as webhooks_router

API_V1_PREFIX = "/api/v1"

api_v1_router = APIRouter(prefix=API_V1_PREFIX)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(organizations_router)
api_v1_router.include_router(incidents_router)
api_v1_router.include_router(integrations_router)
api_v1_router.include_router(github_router)
api_v1_router.include_router(evidence_router)
api_v1_router.include_router(investigations_router)
api_v1_router.include_router(actions_router)
api_v1_router.include_router(webhooks_router)
