"""Role-based access control (RBAC) roles and permission matrix."""

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    ENGINEER = "engineer"
    VIEWER = "viewer"


class Permission(StrEnum):
    INCIDENT_READ = "incident:read"
    INCIDENT_WRITE = "incident:write"
    INCIDENT_ARCHIVE = "incident:archive"
    ORG_READ = "org:read"
    ORG_UPDATE = "org:update"
    MEMBER_READ = "member:read"
    MEMBER_MANAGE = "member:manage"
    MEMBER_MANAGE_PRIVILEGED = "member:manage_privileged"
    INVITATION_READ = "invitation:read"
    INVITATION_MANAGE = "invitation:manage"
    AUDIT_READ = "audit:read"
    INTEGRATION_READ = "integration:read"
    INTEGRATION_MANAGE = "integration:manage"
    EVENT_READ = "event:read"
    EVENT_REPLAY = "event:replay"
    ACTION_READ = "action:read"
    ACTION_PROPOSE = "action:propose"
    ACTION_APPROVE = "action:approve"
    ACTION_EXECUTE = "action:execute"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset(
        {
            Permission.INCIDENT_READ,
            Permission.ORG_READ,
            Permission.MEMBER_READ,
            Permission.ACTION_READ,
        }
    ),
    Role.ENGINEER: frozenset(
        {
            Permission.INCIDENT_READ,
            Permission.INCIDENT_WRITE,
            Permission.ORG_READ,
            Permission.MEMBER_READ,
            Permission.ACTION_READ,
            Permission.ACTION_PROPOSE,
            Permission.ACTION_APPROVE,
            Permission.ACTION_EXECUTE,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Permission.INCIDENT_READ,
            Permission.INCIDENT_WRITE,
            Permission.INCIDENT_ARCHIVE,
            Permission.ORG_READ,
            Permission.MEMBER_READ,
            Permission.MEMBER_MANAGE,
            Permission.INVITATION_READ,
            Permission.INVITATION_MANAGE,
            Permission.AUDIT_READ,
            Permission.INTEGRATION_READ,
            Permission.INTEGRATION_MANAGE,
            Permission.EVENT_READ,
            Permission.EVENT_REPLAY,
            Permission.ACTION_READ,
            Permission.ACTION_PROPOSE,
            Permission.ACTION_APPROVE,
            Permission.ACTION_EXECUTE,
        }
    ),
    Role.OWNER: frozenset(Permission),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
