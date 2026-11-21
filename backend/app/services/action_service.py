"""Domain service for controlled external write actions and human approval gate."""

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.permissions import Permission, Role, has_permission
from app.core.redaction import redact_text, redact_value
from app.core.secrets import decrypt_secret, encrypt_secret
from app.core.telemetry import CONNECTOR_DURATION_SECONDS, CONNECTOR_REQUESTS_TOTAL, get_tracer
from app.integrations.actions.base import (
    ActionPermissionError,
    ActionProvider,
    ActionProviderError,
    ActionTimeoutError,
)
from app.integrations.actions.live_clients import LiveJiraClient, LiveSlackClient
from app.integrations.actions.mock_adapters import MockJiraAdapter, MockSlackAdapter
from app.models.action import (
    ActionConnectorMode,
    ActionProviderType,
    ActionType,
    ExternalActionConnector,
    ProposedAction,
    ProposedActionStatus,
)
from app.models.incident import Incident
from app.models.incident_details import IncidentTimelineEvent
from app.models.membership import Membership
from app.repositories import audit_repo
from app.schemas.action import (
    ActionConnectorCreate,
    ActionConnectorOut,
    ActionConnectorTestOut,
    JiraIssuePayload,
    ProposedActionCreate,
    ProposedActionOut,
    SlackMessagePayload,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def compute_payload_hash(action_type: str, target_destination: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {
            "action_type": action_type,
            "target_destination": target_destination,
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_action_provider(connector: ExternalActionConnector, settings: Settings) -> ActionProvider:
    if connector.mode == ActionConnectorMode.MOCK.value:
        if connector.provider == ActionProviderType.JIRA.value:
            return MockJiraAdapter(allowed_projects=list(connector.allowed_targets_json))
        return MockSlackAdapter(allowed_channels=list(connector.allowed_targets_json))

    if not connector.encrypted_credential:
        raise ValidationError("Live action connector has no encrypted credential configured")
    cred = decrypt_secret(connector.encrypted_credential, settings)
    if connector.provider == ActionProviderType.JIRA.value:
        if not connector.base_url:
            raise ValidationError("Live Jira connector requires base_url")
        return LiveJiraClient(
            base_url=connector.base_url,
            credential=cred,
            timeout_seconds=settings.action_request_timeout_seconds,
        )
    return LiveSlackClient(
        credential=cred,
        timeout_seconds=settings.action_request_timeout_seconds,
    )


def connector_to_out(conn: ExternalActionConnector) -> ActionConnectorOut:
    out = ActionConnectorOut.model_validate(conn)
    out.has_credential = bool(conn.encrypted_credential)
    return out


def action_to_out(action: ProposedAction, *, connector_mode: str) -> ProposedActionOut:
    out = ProposedActionOut.model_validate(action)
    out.connector_mode = connector_mode
    return out


def create_connector(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    data: ActionConnectorCreate,
    settings: Settings | None = None,
) -> ExternalActionConnector:
    cfg = settings or get_settings()
    if data.mode is ActionConnectorMode.LIVE:
        if not data.credential or not data.credential.strip():
            raise ValidationError("Live connector requires a credential/token")
        if data.provider is ActionProviderType.JIRA and not data.base_url:
            raise ValidationError("Live Jira connector requires an https:// base_url")

    existing = db.scalar(
        select(ExternalActionConnector).where(
            ExternalActionConnector.organization_id == organization_id,
            ExternalActionConnector.provider == data.provider.value,
            ExternalActionConnector.name == data.name.strip(),
        )
    )
    if existing is not None:
        raise ConflictError("Action connector with this provider and name already exists")

    encrypted = (
        encrypt_secret(data.credential.strip(), cfg)
        if data.credential and data.credential.strip()
        else None
    )
    perm_summary = (
        {"scope": "write:jira-work", "mode": data.mode.value}
        if data.provider is ActionProviderType.JIRA
        else {"scope": "chat:write", "mode": data.mode.value}
    )

    conn = ExternalActionConnector(
        organization_id=organization_id,
        provider=data.provider.value,
        name=data.name.strip(),
        mode=data.mode.value,
        base_url=data.base_url,
        allowed_targets_json=data.allowed_targets,
        encrypted_credential=encrypted,
        permission_summary_json=perm_summary,
    )
    db.add(conn)
    db.flush()
    audit_repo.append_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="action_connector.created",
        target_type="external_action_connector",
        target_id=str(conn.id),
        metadata={"provider": conn.provider, "mode": conn.mode, "targets": data.allowed_targets},
    )
    db.commit()
    db.refresh(conn)
    return conn


def list_connectors(db: Session, *, organization_id: int) -> list[ExternalActionConnector]:
    return list(
        db.scalars(
            select(ExternalActionConnector)
            .where(ExternalActionConnector.organization_id == organization_id)
            .order_by(ExternalActionConnector.created_at.desc())
        ).all()
    )


def get_connector(
    db: Session, *, organization_id: int, connector_id: int
) -> ExternalActionConnector:
    conn = db.scalar(
        select(ExternalActionConnector).where(
            ExternalActionConnector.id == connector_id,
            ExternalActionConnector.organization_id == organization_id,
        )
    )
    if conn is None:
        raise NotFoundError("Action connector not found")
    return conn


def test_connector(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    connector_id: int,
    settings: Settings | None = None,
) -> ActionConnectorTestOut:
    cfg = settings or get_settings()
    conn = get_connector(db, organization_id=organization_id, connector_id=connector_id)
    now = _utc_now()
    conn.last_test_at = now
    try:
        provider = build_action_provider(conn, cfg)
        res = provider.test_connection()
        conn.last_test_status = "ok"
        conn.last_success_at = now
        conn.last_error = None
        conn.permission_summary_json = res.permission_summary
        audit_repo.append_event(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="action_connector.tested",
            target_type="external_action_connector",
            target_id=str(conn.id),
            metadata={"ok": True, "mode": conn.mode},
        )
        db.commit()
        return ActionConnectorTestOut(
            ok=res.ok,
            mode=res.mode,
            permission_summary=res.permission_summary,
            diagnostics=res.diagnostics,
        )
    except ActionProviderError as exc:
        safe_err = redact_text(str(exc))[:300]
        conn.last_test_status = "failed"
        conn.last_error = safe_err
        db.commit()
        return ActionConnectorTestOut(
            ok=False,
            mode=conn.mode,
            permission_summary=conn.permission_summary_json,
            diagnostics=safe_err,
        )


def propose_action(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    incident_id: int,
    data: ProposedActionCreate,
    settings: Settings | None = None,
) -> tuple[ProposedAction, str]:
    cfg = settings or get_settings()
    incident = db.scalar(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.organization_id == organization_id,
            Incident.archived_at.is_(None),
        )
    )
    if incident is None:
        raise NotFoundError("Incident not found")

    connector = get_connector(db, organization_id=organization_id, connector_id=data.connector_id)
    expected_provider = (
        ActionProviderType.JIRA.value
        if data.action_type is ActionType.JIRA_CREATE_ISSUE
        else ActionProviderType.SLACK.value
    )
    if connector.provider != expected_provider:
        raise ValidationError(
            f"Connector provider '{connector.provider}' does not support '{data.action_type.value}'"
        )

    dest = data.target_destination.strip()
    if dest not in connector.allowed_targets_json:
        raise ValidationError(
            f"Destination '{dest}' is not in connector allowlist: {connector.allowed_targets_json}"
        )

    try:
        if data.action_type is ActionType.JIRA_CREATE_ISSUE:
            validated_payload = JiraIssuePayload.model_validate(data.payload).model_dump()
        else:
            validated_payload = SlackMessagePayload.model_validate(data.payload).model_dump()
    except PydanticValidationError as exc:
        raise ValidationError(f"Invalid action payload: {exc.errors()[0]['msg']}") from exc

    sanitized_payload = redact_value(validated_payload)
    assert isinstance(sanitized_payload, dict)
    payload_hash = compute_payload_hash(data.action_type.value, dest, sanitized_payload)
    ttl = data.ttl_hours or cfg.action_default_ttl_hours
    expires_at = _utc_now() + timedelta(hours=ttl)
    idem_key = (data.idempotency_key or f"act-{uuid.uuid4().hex}").strip()

    existing_idem = db.scalar(
        select(ProposedAction).where(
            ProposedAction.organization_id == organization_id,
            ProposedAction.idempotency_key == idem_key,
        )
    )
    if existing_idem is not None:
        return existing_idem, connector.mode

    action = ProposedAction(
        organization_id=organization_id,
        incident_id=incident.id,
        investigation_id=data.investigation_id,
        connector_id=connector.id,
        action_type=data.action_type.value,
        target_system=connector.provider,
        target_destination=dest,
        payload_preview_json=sanitized_payload,
        payload_hash=payload_hash,
        evidence_links_json=[e.strip()[:200] for e in data.evidence_links if e.strip()],
        requested_by_type=data.requested_by_type,
        requested_by_user_id=actor_user_id,
        status=ProposedActionStatus.PROPOSED.value,
        expires_at=expires_at,
        idempotency_key=idem_key,
        audit_metadata_json={"connector_mode": connector.mode},
    )
    db.add(action)
    db.flush()
    audit_repo.append_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="proposed_action.created",
        target_type="proposed_action",
        target_id=str(action.id),
        metadata={
            "incident_id": incident.id,
            "action_type": action.action_type,
            "destination": dest,
            "connector_mode": connector.mode,
        },
    )
    db.commit()
    db.refresh(action)
    return action, connector.mode


def list_actions(
    db: Session,
    *,
    organization_id: int,
    incident_id: int | None = None,
    status_filter: ProposedActionStatus | None = None,
) -> list[tuple[ProposedAction, str]]:
    if incident_id is not None:
        inc_exists = db.scalar(
            select(Incident.id).where(
                Incident.id == incident_id,
                Incident.organization_id == organization_id,
                Incident.archived_at.is_(None),
            )
        )
        if inc_exists is None:
            raise NotFoundError("Incident not found")
    stmt = (
        select(ProposedAction, ExternalActionConnector.mode)
        .join(ExternalActionConnector, ProposedAction.connector_id == ExternalActionConnector.id)
        .where(ProposedAction.organization_id == organization_id)
    )
    if incident_id is not None:
        stmt = stmt.where(ProposedAction.incident_id == incident_id)
    if status_filter is not None:
        stmt = stmt.where(ProposedAction.status == status_filter.value)
    rows = db.execute(stmt.order_by(ProposedAction.created_at.desc())).all()
    return [(row[0], str(row[1])) for row in rows]


def get_action(
    db: Session, *, organization_id: int, action_id: int
) -> tuple[ProposedAction, ExternalActionConnector]:
    row = db.execute(
        select(ProposedAction, ExternalActionConnector)
        .join(ExternalActionConnector, ProposedAction.connector_id == ExternalActionConnector.id)
        .where(
            ProposedAction.id == action_id,
            ProposedAction.organization_id == organization_id,
        )
    ).first()
    if row is None:
        raise NotFoundError("Proposed action not found")
    return row[0], row[1]


def approve_action(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action_id: int,
    settings: Settings | None = None,
) -> tuple[ProposedAction, str]:
    cfg = settings or get_settings()
    action, conn = get_action(db, organization_id=organization_id, action_id=action_id)
    if action.status != ProposedActionStatus.PROPOSED.value:
        raise ConflictError(f"Cannot approve action in '{action.status}' state")

    now = _utc_now()
    if now > _as_utc(action.expires_at):
        action.status = ProposedActionStatus.EXPIRED.value
        db.commit()
        raise ConflictError("Proposed action has expired and cannot be approved")

    if (
        not cfg.action_allow_self_approval
        and action.requested_by_type == "user"
        and action.requested_by_user_id == actor_user_id
    ):
        raise ForbiddenError(
            "Separation of duties: proposer cannot self-approve this external action"
        )

    action.status = ProposedActionStatus.APPROVED.value
    action.approved_by_user_id = actor_user_id
    action.approved_at = now
    audit_repo.append_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="proposed_action.approved",
        target_type="proposed_action",
        target_id=str(action.id),
        metadata={"destination": action.target_destination, "payload_hash": action.payload_hash},
    )
    db.commit()
    db.refresh(action)
    return action, conn.mode


def reject_action(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action_id: int,
    reason: str,
) -> tuple[ProposedAction, str]:
    action, conn = get_action(db, organization_id=organization_id, action_id=action_id)
    if action.status not in {
        ProposedActionStatus.PROPOSED.value,
        ProposedActionStatus.APPROVED.value,
    }:
        raise ConflictError(f"Cannot reject action in '{action.status}' state")

    action.status = ProposedActionStatus.REJECTED.value
    action.rejected_by_user_id = actor_user_id
    action.rejected_at = _utc_now()
    action.rejection_reason = reason.strip()
    audit_repo.append_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="proposed_action.rejected",
        target_type="proposed_action",
        target_id=str(action.id),
        metadata={"reason": action.rejection_reason},
    )
    db.commit()
    db.refresh(action)
    return action, conn.mode


def _reverify_execution_auth(db: Session, *, organization_id: int, actor_user_id: int) -> None:
    """Re-check DB tenant membership and ACTION_EXECUTE permission at execution time."""
    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == actor_user_id,
        )
    )
    if membership is None:
        raise ForbiddenError("User is no longer a member of this organization")
    if not has_permission(Role(membership.role), Permission.ACTION_EXECUTE):
        raise ForbiddenError("User lacks permission to execute external actions")


def execute_action(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action_id: int,
    settings: Settings | None = None,
    provider_override: ActionProvider | None = None,
) -> tuple[ProposedAction, str]:
    cfg = settings or get_settings()
    _reverify_execution_auth(db, organization_id=organization_id, actor_user_id=actor_user_id)

    action, conn = get_action(db, organization_id=organization_id, action_id=action_id)
    if action.status == ProposedActionStatus.SUCCEEDED.value:
        return action, conn.mode

    if action.status not in {
        ProposedActionStatus.APPROVED.value,
        ProposedActionStatus.FAILED.value,
    }:
        raise ConflictError(
            f"Action in '{action.status}' state cannot execute; explicit approval is required"
        )

    now = _utc_now()
    if now > _as_utc(action.expires_at):
        action.status = ProposedActionStatus.EXPIRED.value
        db.commit()
        raise ConflictError("Approval has expired; propose a new action")

    current_hash = compute_payload_hash(
        action.action_type, action.target_destination, action.payload_preview_json
    )
    if current_hash != action.payload_hash:
        action.status = ProposedActionStatus.FAILED.value
        action.last_error = "Payload integrity check failed: payload modified after approval"
        audit_repo.append_event(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="proposed_action.integrity_failed",
            target_type="proposed_action",
            target_id=str(action.id),
            metadata={"expected_hash": action.payload_hash, "actual_hash": current_hash},
        )
        db.commit()
        raise ConflictError(action.last_error)

    action.status = ProposedActionStatus.EXECUTING.value
    db.flush()

    provider = provider_override or build_action_provider(conn, cfg)
    max_attempts = 1 + cfg.action_max_execution_retries
    last_exc_msg: str | None = None
    tracer = get_tracer("opspilot.actions")

    for _attempt in range(1, max_attempts + 1):
        action.execution_attempts += 1
        t_call = time.perf_counter()
        try:
            with tracer.start_as_current_span(f"connector.{conn.provider}.execute"):
                res = provider.execute_action(
                    action_type=action.action_type,
                    destination=action.target_destination,
                    payload=action.payload_preview_json,
                    idempotency_key=action.idempotency_key,
                )
            CONNECTOR_DURATION_SECONDS.labels(provider=conn.provider, mode=conn.mode).observe(
                time.perf_counter() - t_call
            )
            CONNECTOR_REQUESTS_TOTAL.labels(
                provider=conn.provider, mode=conn.mode, outcome="success"
            ).inc()
            action.status = ProposedActionStatus.SUCCEEDED.value
            action.external_id = res.external_id
            action.external_url = res.external_url
            action.execution_result_json = res.response_summary
            action.last_error = None
            action.executed_at = _utc_now()
            conn.last_success_at = action.executed_at
            conn.last_error = None

            db.add(
                IncidentTimelineEvent(
                    organization_id=organization_id,
                    incident_id=action.incident_id,
                    actor_user_id=actor_user_id,
                    event_type="external_action_executed",
                    message=(
                        f"Executed {action.action_type} -> {action.target_destination} "
                        f"({res.external_id})"
                    ),
                    details_json={
                        "proposed_action_id": action.id,
                        "external_id": res.external_id,
                        "is_mock": res.is_mock,
                    },
                )
            )
            audit_repo.append_event(
                db,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="proposed_action.executed",
                target_type="proposed_action",
                target_id=str(action.id),
                metadata={
                    "external_id": res.external_id,
                    "is_mock": res.is_mock,
                    "attempts": action.execution_attempts,
                },
            )
            db.commit()
            db.refresh(action)
            return action, conn.mode
        except ActionTimeoutError as exc:
            CONNECTOR_DURATION_SECONDS.labels(provider=conn.provider, mode=conn.mode).observe(
                time.perf_counter() - t_call
            )
            CONNECTOR_REQUESTS_TOTAL.labels(
                provider=conn.provider, mode=conn.mode, outcome="timeout"
            ).inc()
            last_exc_msg = redact_text(str(exc))[:300]
            continue
        except (ActionPermissionError, ActionProviderError) as exc:
            CONNECTOR_DURATION_SECONDS.labels(provider=conn.provider, mode=conn.mode).observe(
                time.perf_counter() - t_call
            )
            CONNECTOR_REQUESTS_TOTAL.labels(
                provider=conn.provider, mode=conn.mode, outcome="error"
            ).inc()
            last_exc_msg = redact_text(str(exc))[:300]
            break

    action.status = ProposedActionStatus.FAILED.value
    action.last_error = last_exc_msg or "External action execution failed"
    conn.last_error = action.last_error
    audit_repo.append_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="proposed_action.failed",
        target_type="proposed_action",
        target_id=str(action.id),
        metadata={"error": action.last_error, "attempts": action.execution_attempts},
    )
    db.commit()
    db.refresh(action)
    return action, conn.mode
