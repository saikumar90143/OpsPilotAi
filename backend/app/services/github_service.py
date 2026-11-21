"""Read-only GitHub connector management, correlation, and webhook ingestion."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2 as httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, UnauthorizedError
from app.core.logging import redact
from app.core.secrets import decrypt_secret, encrypt_secret, verify_github_webhook_signature
from app.integrations.scm.base import (
    ScmAuthType,
    ScmConnectionCheck,
    ScmMode,
    ScmProviderError,
    SourceControlProvider,
)
from app.integrations.scm.github_client import GitHubClient
from app.integrations.scm.mock_github import MockGitHubAdapter
from app.models.audit_log import AuditLog
from app.models.github_connector import GitHubConnector
from app.models.incident_details import EvidenceKind, IncidentEvidenceRef, IncidentTimelineEvent
from app.repositories import audit_repo
from app.schemas.github import GitHubConnectorCreate, GitHubConnectorRead, GitHubConnectorUpdate
from app.services import incidents as incident_service

CONNECTOR_NOT_FOUND = "GitHub connector not found"
HYPOTHESIS_DISCLAIMER = (
    "Correlation hypothesis only — time/service proximity is not proof of causation."
)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def to_connector_read(c: GitHubConnector) -> GitHubConnectorRead:
    return GitHubConnectorRead(
        id=c.id,
        organization_id=c.organization_id,
        name=c.name,
        mode=ScmMode(c.mode),
        auth_type=ScmAuthType(c.auth_type),
        github_app_id=c.github_app_id,
        github_installation_id=c.github_installation_id,
        has_credential=bool(c.encrypted_credential),
        has_webhook_secret=bool(c.encrypted_webhook_secret),
        webhook_path=f"/api/v1/webhooks/github/{c.webhook_endpoint_token}",
        service_repo_map=dict(c.service_repo_map_json),
        is_enabled=c.is_enabled,
        last_test_status=c.last_test_status,
        last_test_at=c.last_test_at,
        last_success_at=c.last_success_at,
        last_error=c.last_error,
        permission_summary=dict(c.permission_summary_json),
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def create_connector(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    data: GitHubConnectorCreate,
    settings: Settings,
    ip_address: str | None = None,
) -> GitHubConnector:
    if data.mode is ScmMode.LIVE and not data.credential:
        raise ConflictError("Live GitHub connector requires a credential (App PEM or PAT)")
    if data.auth_type is ScmAuthType.GITHUB_APP and (
        not data.github_app_id or not data.github_installation_id
    ):
        raise ConflictError("GitHub App auth requires github_app_id and github_installation_id")

    connector = GitHubConnector(
        organization_id=organization_id,
        name=data.name.strip(),
        mode=data.mode.value,
        auth_type=(ScmAuthType.MOCK.value if data.mode is ScmMode.MOCK else data.auth_type.value),
        github_app_id=data.github_app_id,
        github_installation_id=data.github_installation_id,
        encrypted_credential=(
            encrypt_secret(data.credential, settings) if data.credential else None
        ),
        encrypted_webhook_secret=(
            encrypt_secret(data.webhook_secret, settings) if data.webhook_secret else None
        ),
        webhook_endpoint_token=secrets.token_urlsafe(18),
        service_repo_map_json=data.service_repo_map,
        is_enabled=True,
    )
    db.add(connector)
    db.flush()
    audit_repo.append_event(
        db,
        action="github.connector_created",
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_type="github_connector",
        target_id=connector.id,
        ip_address=ip_address,
        metadata={"mode": connector.mode, "auth_type": connector.auth_type},
    )
    db.commit()
    db.refresh(connector)
    return connector


def list_connectors(db: Session, *, organization_id: int) -> list[GitHubConnector]:
    stmt = (
        select(GitHubConnector)
        .where(GitHubConnector.organization_id == organization_id)
        .order_by(GitHubConnector.id.asc())
    )
    return list(db.scalars(stmt).all())


def get_connector(db: Session, *, organization_id: int, connector_id: int) -> GitHubConnector:
    connector = db.scalar(
        select(GitHubConnector).where(
            GitHubConnector.id == connector_id,
            GitHubConnector.organization_id == organization_id,
        )
    )
    if connector is None:
        raise NotFoundError(CONNECTOR_NOT_FOUND)
    return connector


def update_connector(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    connector_id: int,
    data: GitHubConnectorUpdate,
    ip_address: str | None = None,
) -> GitHubConnector:
    connector = get_connector(db, organization_id=organization_id, connector_id=connector_id)
    if data.name is not None:
        connector.name = data.name.strip()
    if data.is_enabled is not None:
        connector.is_enabled = data.is_enabled
    if data.service_repo_map is not None:
        connector.service_repo_map_json = data.service_repo_map
    audit_repo.append_event(
        db,
        action="github.connector_updated",
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_type="github_connector",
        target_id=connector.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(connector)
    return connector


def build_provider(
    connector: GitHubConnector,
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> SourceControlProvider:
    if connector.mode == ScmMode.MOCK.value:
        return MockGitHubAdapter()
    if not connector.encrypted_credential:
        raise ConflictError("Live GitHub connector has no stored credential")
    credential = decrypt_secret(connector.encrypted_credential, settings)
    return GitHubClient(
        auth_type=ScmAuthType(connector.auth_type),
        credential=credential,
        app_id=connector.github_app_id,
        installation_id=connector.github_installation_id,
        base_url=settings.github_api_base_url,
        timeout_seconds=settings.github_request_timeout_seconds,
        transport=transport,
    )


def test_connector(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    connector_id: int,
    settings: Settings,
    transport: httpx.BaseTransport | None = None,
    ip_address: str | None = None,
) -> ScmConnectionCheck:
    connector = get_connector(db, organization_id=organization_id, connector_id=connector_id)
    provider = build_provider(connector, settings, transport=transport)
    check = provider.test_connection()
    now = datetime.now(UTC)

    connector.last_test_at = now
    connector.permission_summary_json = check.permission_summary
    if check.ok:
        connector.last_test_status = "ok"
        connector.last_success_at = now
        connector.last_error = None
    else:
        connector.last_test_status = "error"
        connector.last_error = redact(check.diagnostics)[:500]

    audit_repo.append_event(
        db,
        action="github.connector_tested",
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_type="github_connector",
        target_id=connector.id,
        ip_address=ip_address,
        metadata={"ok": check.ok, "mode": check.mode.value},
    )
    db.commit()
    return check


def correlate_incident(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    incident_id: int,
    repository_override: str | None,
    lookback_hours: int,
    settings: Settings,
    transport: httpx.BaseTransport | None = None,
    ip_address: str | None = None,
) -> tuple[ScmMode, str, datetime, datetime, list[IncidentEvidenceRef]]:
    incident = incident_service.get_incident(
        db, organization_id=organization_id, incident_id=incident_id
    )
    connector = db.scalar(
        select(GitHubConnector)
        .where(
            GitHubConnector.organization_id == organization_id,
            GitHubConnector.is_enabled.is_(True),
        )
        .order_by(GitHubConnector.id.asc())
    )
    if connector is None:
        raise NotFoundError("No enabled GitHub connector configured for this organization")

    repo_full = repository_override or connector.service_repo_map_json.get(incident.service)
    if not repo_full:
        if connector.mode == ScmMode.MOCK.value:
            repo_full = f"demo-org/{incident.service}"
        else:
            raise ConflictError(
                f"No repository mapped for service '{incident.service}'; pass repository explicitly"
            )

    owner, repo = repo_full.split("/", 1)
    provider = build_provider(connector, settings, transport=transport)
    inc_created = _as_utc(incident.created_at)
    window_start = inc_created - timedelta(hours=lookback_hours)
    window_end = inc_created + timedelta(hours=1)

    try:
        commits = provider.list_commits(owner, repo, since=window_start, until=window_end).items
        prs = provider.list_pull_requests(owner, repo, since=window_start, until=window_end).items
        deployments = provider.list_deployments(
            owner, repo, since=window_start, until=window_end
        ).items
    except ScmProviderError as exc:
        connector.last_error = redact(str(exc))[:500]
        connector.last_test_status = "error"
        db.commit()
        raise ConflictError(f"GitHub read failed: {exc}") from exc

    created_refs: list[IncidentEvidenceRef] = []
    mode_label = "DEMO/MOCK" if provider.mode is ScmMode.MOCK else "LIVE"

    for c in commits[:5]:
        rationale = (
            f"Committed to {c.repository} within {lookback_hours}h before incident creation."
        )
        ref = IncidentEvidenceRef(
            organization_id=organization_id,
            incident_id=incident.id,
            added_by_user_id=actor_user_id,
            kind=EvidenceKind.COMMIT.value,
            title=f"[{mode_label}] Commit {c.sha[:7]}: {c.message}"[:200],
            uri=c.html_url,
            summary=f"{HYPOTHESIS_DISCLAIMER} {rationale} (author: {c.author})",
            metadata_json={
                "hypothesis": True,
                "disclaimer": HYPOTHESIS_DISCLAIMER,
                "mode": provider.mode.value,
                "repository": c.repository,
                "identifier": c.sha[:12],
                "author": c.author,
                "timestamp": c.committed_at.isoformat(),
                "rationale": rationale,
            },
        )
        db.add(ref)
        created_refs.append(ref)

    for pr in prs[:5]:
        ts = pr.merged_at or pr.created_at
        rationale = f"Pull request #{pr.number} active/merged near incident window."
        ref = IncidentEvidenceRef(
            organization_id=organization_id,
            incident_id=incident.id,
            added_by_user_id=actor_user_id,
            kind=EvidenceKind.LINK.value,
            title=f"[{mode_label}] PR #{pr.number}: {pr.title}"[:200],
            uri=pr.html_url,
            summary=f"{HYPOTHESIS_DISCLAIMER} {rationale} (author: {pr.author})",
            metadata_json={
                "hypothesis": True,
                "disclaimer": HYPOTHESIS_DISCLAIMER,
                "mode": provider.mode.value,
                "repository": pr.repository,
                "identifier": f"PR#{pr.number}",
                "author": pr.author,
                "timestamp": ts.isoformat(),
                "reviews": [{"author": r.author, "state": r.state} for r in pr.reviews],
                "rationale": rationale,
            },
        )
        db.add(ref)
        created_refs.append(ref)

    for dep in deployments[:3]:
        rationale = f"Deployment to '{dep.environment}' recorded near incident window."
        ref = IncidentEvidenceRef(
            organization_id=organization_id,
            incident_id=incident.id,
            added_by_user_id=actor_user_id,
            kind=EvidenceKind.LINK.value,
            title=f"[{mode_label}] Deploy #{dep.id} ({dep.environment}, {dep.ref})"[:200],
            uri=dep.html_url,
            summary=f"{HYPOTHESIS_DISCLAIMER} {rationale} (creator: {dep.creator})",
            metadata_json={
                "hypothesis": True,
                "disclaimer": HYPOTHESIS_DISCLAIMER,
                "mode": provider.mode.value,
                "repository": dep.repository,
                "identifier": f"deploy#{dep.id}",
                "author": dep.creator,
                "timestamp": dep.created_at.isoformat(),
                "environment": dep.environment,
                "rationale": rationale,
            },
        )
        db.add(ref)
        created_refs.append(ref)

    db.flush()
    db.add(
        IncidentTimelineEvent(
            organization_id=organization_id,
            incident_id=incident.id,
            actor_user_id=actor_user_id,
            event_type="incident.github_correlated",
            message=(
                f"Attached {len(created_refs)} GitHub correlation hypotheses ({mode_label}) "
                f"for {repo_full}"
            ),
            details_json={"repository": repo_full, "mode": provider.mode.value},
        )
    )
    audit_repo.append_event(
        db,
        action="incident.github_correlated",
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_type="incident",
        target_id=incident.id,
        ip_address=ip_address,
        metadata={"repository": repo_full, "mode": provider.mode.value, "count": len(created_refs)},
    )
    db.commit()
    for ref in created_refs:
        db.refresh(ref)
    return provider.mode, repo_full, window_start, window_end, created_refs


def receive_github_webhook(
    db: Session,
    *,
    endpoint_token: str,
    delivery_id: str | None,
    event_name: str | None,
    raw_body: bytes,
    raw_payload: dict[str, Any],
    signature_header: str | None,
    settings: Settings,
    ip_address: str | None = None,
) -> tuple[bool, int]:
    """Verify X-Hub-Signature-256 and deduplicate by X-GitHub-Delivery (read-only receipt)."""
    connector = db.scalar(
        select(GitHubConnector).where(
            GitHubConnector.webhook_endpoint_token == endpoint_token,
            GitHubConnector.is_enabled.is_(True),
        )
    )
    if connector is None:
        raise NotFoundError(CONNECTOR_NOT_FOUND)
    if not connector.encrypted_webhook_secret:
        raise UnauthorizedError("GitHub webhook secret not configured")

    secret = decrypt_secret(connector.encrypted_webhook_secret, settings)
    verify_github_webhook_signature(
        raw_body=raw_body, signature_header=signature_header, secret=secret
    )
    if not delivery_id or not event_name:
        raise ConflictError("Missing X-GitHub-Delivery or X-GitHub-Event header")

    existing = db.scalar(
        select(AuditLog).where(
            AuditLog.organization_id == connector.organization_id,
            AuditLog.action == "github.webhook_received",
            AuditLog.target_type == "github_delivery",
            AuditLog.target_id == delivery_id[:64],
        )
    )
    if existing is not None:
        return True, existing.id

    repo_name = str((raw_payload.get("repository") or {}).get("full_name") or "unknown")
    entry = audit_repo.append_event(
        db,
        action="github.webhook_received",
        organization_id=connector.organization_id,
        target_type="github_delivery",
        target_id=delivery_id[:64],
        ip_address=ip_address,
        metadata={
            "connector_id": connector.id,
            "event": event_name,
            "repository": repo_name,
        },
    )
    db.commit()
    db.refresh(entry)
    return False, entry.id
