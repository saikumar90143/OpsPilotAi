"""External action connector and human-gated ProposedAction API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AppSettings, DbSession, require_permission
from app.api.errors import ERROR_RESPONSES
from app.core.permissions import Permission
from app.models.action import ProposedActionStatus
from app.schemas.action import (
    ActionConnectorCreate,
    ActionConnectorOut,
    ActionConnectorTestOut,
    ProposedActionCreate,
    ProposedActionOut,
    ProposedActionRejectRequest,
)
from app.services import action_service
from app.services.auth_service import AuthContext

router = APIRouter(tags=["actions"], responses=ERROR_RESPONSES)


@router.get("/action-connectors", response_model=list[ActionConnectorOut])
def list_action_connectors(
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.ACTION_READ))],
) -> list[ActionConnectorOut]:
    conns = action_service.list_connectors(db, organization_id=auth.organization.id)
    return [action_service.connector_to_out(c) for c in conns]


@router.post(
    "/action-connectors",
    response_model=ActionConnectorOut,
    status_code=status.HTTP_201_CREATED,
)
def create_action_connector(
    payload: ActionConnectorCreate,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> ActionConnectorOut:
    conn = action_service.create_connector(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        data=payload,
        settings=settings,
    )
    return action_service.connector_to_out(conn)


@router.post("/action-connectors/{connector_id}/test", response_model=ActionConnectorTestOut)
def test_action_connector(
    connector_id: int,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> ActionConnectorTestOut:
    return action_service.test_connector(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        connector_id=connector_id,
        settings=settings,
    )


@router.post(
    "/incidents/{incident_id}/actions",
    response_model=ProposedActionOut,
    status_code=status.HTTP_201_CREATED,
)
def propose_action(
    incident_id: int,
    payload: ProposedActionCreate,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.ACTION_PROPOSE))],
) -> ProposedActionOut:
    action, mode = action_service.propose_action(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        data=payload,
        settings=settings,
    )
    return action_service.action_to_out(action, connector_mode=mode)


@router.get("/incidents/{incident_id}/actions", response_model=list[ProposedActionOut])
def list_incident_actions(
    incident_id: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.ACTION_READ))],
) -> list[ProposedActionOut]:
    rows = action_service.list_actions(
        db, organization_id=auth.organization.id, incident_id=incident_id
    )
    return [action_service.action_to_out(a, connector_mode=m) for a, m in rows]


@router.get("/actions", response_model=list[ProposedActionOut])
def list_org_actions(
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.ACTION_READ))],
    status_filter: ProposedActionStatus | None = Query(default=None, alias="status"),
) -> list[ProposedActionOut]:
    rows = action_service.list_actions(
        db, organization_id=auth.organization.id, status_filter=status_filter
    )
    return [action_service.action_to_out(a, connector_mode=m) for a, m in rows]


@router.post("/actions/{action_id}/approve", response_model=ProposedActionOut)
def approve_action(
    action_id: int,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.ACTION_APPROVE))],
) -> ProposedActionOut:
    action, mode = action_service.approve_action(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        action_id=action_id,
        settings=settings,
    )
    return action_service.action_to_out(action, connector_mode=mode)


@router.post("/actions/{action_id}/reject", response_model=ProposedActionOut)
def reject_action(
    action_id: int,
    payload: ProposedActionRejectRequest,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.ACTION_APPROVE))],
) -> ProposedActionOut:
    action, mode = action_service.reject_action(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        action_id=action_id,
        reason=payload.reason,
    )
    return action_service.action_to_out(action, connector_mode=mode)


@router.post("/actions/{action_id}/execute", response_model=ProposedActionOut)
def execute_action(
    action_id: int,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.ACTION_EXECUTE))],
) -> ProposedActionOut:
    action, mode = action_service.execute_action(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        action_id=action_id,
        settings=settings,
    )
    return action_service.action_to_out(action, connector_mode=mode)
