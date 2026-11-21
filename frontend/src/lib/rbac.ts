import type { IncidentStatus, Role } from "./types";

export type Permission =
  | "incident:read"
  | "incident:write"
  | "incident:archive"
  | "org:read"
  | "org:update"
  | "member:read"
  | "member:manage"
  | "audit:read"
  | "integration:read"
  | "integration:manage"
  | "event:read"
  | "event:replay";

const ROLE_PERMISSIONS: Record<Role, ReadonlySet<Permission>> = {
  viewer: new Set(["incident:read", "org:read", "member:read"]),
  engineer: new Set(["incident:read", "incident:write", "org:read", "member:read"]),
  admin: new Set([
    "incident:read",
    "incident:write",
    "incident:archive",
    "org:read",
    "member:read",
    "member:manage",
    "audit:read",
    "integration:read",
    "integration:manage",
    "event:read",
    "event:replay",
  ]),
  owner: new Set([
    "incident:read",
    "incident:write",
    "incident:archive",
    "org:read",
    "org:update",
    "member:read",
    "member:manage",
    "audit:read",
    "integration:read",
    "integration:manage",
    "event:read",
    "event:replay",
  ]),
};

export function hasPermission(role: Role | undefined, permission: Permission): boolean {
  if (!role) return false;
  return ROLE_PERMISSIONS[role].has(permission);
}

export const ALLOWED_TRANSITIONS: Record<IncidentStatus, readonly IncidentStatus[]> = {
  open: ["acknowledged", "investigating", "resolved", "closed"],
  acknowledged: ["investigating", "resolved", "closed"],
  investigating: ["acknowledged", "resolved", "closed"],
  resolved: ["open", "investigating", "closed"],
  closed: ["open"],
};

export function canTransition(from: IncidentStatus, to: IncidentStatus): boolean {
  return ALLOWED_TRANSITIONS[from].includes(to);
}
