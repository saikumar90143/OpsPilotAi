"""Read-only GitHub connector configuration and test-connection endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import AppSettings, DbSession, get_client_ip, require_permission
from app.api.errors import ERROR_RESPONSES
from app.core.permissions import Permission
from app.schemas.github import (
    GitHubConnectionTestRead,
    GitHubConnectorCreate,
    GitHubConnectorRead,
    GitHubConnectorUpdate,
)
from app.services import github_service
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/github", tags=["github"], responses=ERROR_RESPONSES)


@router.post(
    "/connectors",
    response_model=GitHubConnectorRead,
    status_code=status.HTTP_201_CREATED,
)
def create_github_connector(
    payload: GitHubConnectorCreate,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> GitHubConnectorRead:
    connector = github_service.create_connector(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        data=payload,
        settings=settings,
        ip_address=get_client_ip(request),
    )
    return github_service.to_connector_read(connector)


@router.get("/connectors", response_model=list[GitHubConnectorRead])
def list_github_connectors(
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_READ))],
) -> list[GitHubConnectorRead]:
    rows = github_service.list_connectors(db, organization_id=auth.organization.id)
    return [github_service.to_connector_read(c) for c in rows]


@router.patch("/connectors/{connector_id}", response_model=GitHubConnectorRead)
def update_github_connector(
    connector_id: int,
    payload: GitHubConnectorUpdate,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> GitHubConnectorRead:
    connector = github_service.update_connector(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        connector_id=connector_id,
        data=payload,
        ip_address=get_client_ip(request),
    )
    return github_service.to_connector_read(connector)


@router.post("/connectors/{connector_id}/test", response_model=GitHubConnectionTestRead)
def test_github_connector(
    connector_id: int,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> GitHubConnectionTestRead:
    check = github_service.test_connector(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        connector_id=connector_id,
        settings=settings,
        ip_address=get_client_ip(request),
    )
    return GitHubConnectionTestRead(**check.model_dump())
