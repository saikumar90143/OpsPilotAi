import type {
  ActionConnector,
  ActionConnectorTest,
  ActionProviderType,
  ActionType,
  AIStatus,
  ApiErrorBody,
  AuditLog,
  AuthSession,
  Comment,
  CorrelateGitHubResponse,
  Environment,
  EvidenceKind,
  EvidenceRef,
  GitHubConnectionTest,
  GitHubConnector,
  InboundEvent,
  InboundEventStatus,
  Incident,
  IncidentEvidenceContext,
  IncidentStatus,
  Integration,
  IntegrationCreated,
  InvestigationRun,
  KnowledgeDocument,
  KnowledgeSearchResponse,
  LogSearchResponse,
  LogSeverity,
  Membership,
  Organization,
  ProposedAction,
  ProposedActionStatus,
  Role,
  ScmAuthType,
  ScmMode,
  SecretRotated,
  Severity,
  TimelineEvent,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CSRF_COOKIE_NAME = "opspilot_csrf";
const STATE_CHANGING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string;

  constructor(status: number, code: string, message: string, requestId: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return null;
}

let refreshPromise: Promise<boolean> | null = null;

async function attemptTokenRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    const csrf = readCookie(CSRF_COOKIE_NAME);
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: csrf ? { "X-CSRF-Token": csrf } : {},
    });
    return res.ok;
  })().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

async function rawFetch(
  path: string,
  init: RequestInit = {},
  retryOn401 = true,
): Promise<Response> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (STATE_CHANGING_METHODS.has(method)) {
    const csrf = readCookie(CSRF_COOKIE_NAME);
    if (csrf) {
      headers.set("X-CSRF-Token", csrf);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    method,
    headers,
    credentials: "include",
  });

  if (
    response.status === 401 &&
    retryOn401 &&
    !path.startsWith("/api/v1/auth/login") &&
    !path.startsWith("/api/v1/auth/refresh")
  ) {
    const refreshed = await attemptTokenRefresh();
    if (refreshed) {
      return rawFetch(path, init, false);
    }
  }

  if (!response.ok) {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = (await response.json()) as Partial<ApiErrorBody>;
    } catch {
      // Non-JSON error response
    }
    throw new ApiClientError(
      response.status,
      body.error ?? "http_error",
      body.message ?? `Request failed with status ${response.status}`,
      body.request_id ?? response.headers.get("X-Request-ID") ?? "-",
    );
  }

  return response;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await rawFetch(path, init);
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export interface IncidentListParams {
  limit?: number;
  offset?: number;
  status?: IncidentStatus | "";
  severity?: Severity | "";
  environment?: Environment | "";
  service?: string;
  tag?: string;
  q?: string;
  created_after?: string;
  sort_by?: "created_at" | "updated_at" | "severity" | "status";
  sort_order?: "asc" | "desc";
}

export const api = {
  login: (email: string, password: string, organization_slug?: string) =>
    apiFetch<AuthSession>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        ...(organization_slug ? { organization_slug } : {}),
      }),
    }),

  logout: () => apiFetch<void>("/api/v1/auth/logout", { method: "POST" }),

  me: () => apiFetch<AuthSession>("/api/v1/auth/me"),

  listIncidents: async (
    params: IncidentListParams = {},
  ): Promise<{ items: Incident[]; total: number }> => {
    const qs = new URLSearchParams();
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined && val !== "") {
        qs.set(key, String(val));
      }
    }
    const query = qs.toString();
    const res = await rawFetch(`/api/v1/incidents${query ? `?${query}` : ""}`);
    const items = (await res.json()) as Incident[];
    const total = Number(res.headers.get("X-Total-Count") ?? items.length);
    return { items, total };
  },

  getIncident: (id: number) => apiFetch<Incident>(`/api/v1/incidents/${id}`),

  createIncident: (payload: {
    title: string;
    description: string;
    service: string;
    environment: Environment;
    severity: Severity;
    tags: string[];
  }) =>
    apiFetch<Incident>("/api/v1/incidents", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  transitionIncidentStatus: (id: number, status: IncidentStatus, version: number) =>
    apiFetch<Incident>(`/api/v1/incidents/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, version }),
    }),

  acknowledgeIncident: (id: number, version: number, note?: string) =>
    apiFetch<Incident>(`/api/v1/incidents/${id}/acknowledge`, {
      method: "POST",
      body: JSON.stringify({ version, ...(note ? { note } : {}) }),
    }),

  resolveIncident: (id: number, version: number, note?: string) =>
    apiFetch<Incident>(`/api/v1/incidents/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ version, ...(note ? { note } : {}) }),
    }),

  reopenIncident: (id: number, version: number, note?: string) =>
    apiFetch<Incident>(`/api/v1/incidents/${id}/reopen`, {
      method: "POST",
      body: JSON.stringify({ version, ...(note ? { note } : {}) }),
    }),

  assignIncident: (id: number, assignee_user_id: number | null, version: number) =>
    apiFetch<Incident>(`/api/v1/incidents/${id}/assign`, {
      method: "POST",
      body: JSON.stringify({ assignee_user_id, version }),
    }),

  archiveIncident: (id: number) =>
    apiFetch<void>(`/api/v1/incidents/${id}`, { method: "DELETE" }),

  listTimeline: (id: number) => apiFetch<TimelineEvent[]>(`/api/v1/incidents/${id}/timeline`),

  listComments: (id: number) => apiFetch<Comment[]>(`/api/v1/incidents/${id}/comments`),

  addComment: (id: number, body: string) =>
    apiFetch<Comment>(`/api/v1/incidents/${id}/comments`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }),

  listEvidence: (id: number) => apiFetch<EvidenceRef[]>(`/api/v1/incidents/${id}/evidence`),

  addEvidence: (
    id: number,
    payload: { kind: EvidenceKind; title: string; uri?: string; summary: string },
  ) =>
    apiFetch<EvidenceRef>(`/api/v1/incidents/${id}/evidence`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listMemberships: () => apiFetch<Membership[]>("/api/v1/memberships"),

  updateMembershipRole: (membershipId: number, role: Role) =>
    apiFetch<Membership>(`/api/v1/memberships/${membershipId}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),

  updateOrganization: (name: string) =>
    apiFetch<Organization>("/api/v1/organizations/current", {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),

  listAuditLogs: (limit = 50) => apiFetch<AuditLog[]>(`/api/v1/audit-logs?limit=${limit}`),

  listIntegrations: () => apiFetch<Integration[]>("/api/v1/integrations"),

  createIntegration: (name: string, is_simulator_mode: boolean) =>
    apiFetch<IntegrationCreated>("/api/v1/integrations", {
      method: "POST",
      body: JSON.stringify({ provider: "alertmanager", name, is_simulator_mode }),
    }),

  rotateIntegrationSecret: (id: number) =>
    apiFetch<SecretRotated>(`/api/v1/integrations/${id}/rotate-secret`, { method: "POST" }),

  simulateWebhook: (id: number, scenario: "high_error_rate" | "queue_backlog", status: "firing" | "resolved") =>
    apiFetch<{ accepted: boolean; duplicate: boolean; event_ids: number[]; status: string }>(
      `/api/v1/integrations/${id}/simulate`,
      {
        method: "POST",
        body: JSON.stringify({ scenario, status }),
      },
    ),

  listEvents: (params: { status?: InboundEventStatus | ""; is_simulated?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.is_simulated === "true" || params.is_simulated === "false") {
      qs.set("is_simulated", params.is_simulated);
    }
    const q = qs.toString();
    return apiFetch<InboundEvent[]>(`/api/v1/events${q ? `?${q}` : ""}`);
  },

  replayEvent: (id: number) =>
    apiFetch<InboundEvent>(`/api/v1/events/${id}/replay`, { method: "POST" }),

  listGitHubConnectors: () => apiFetch<GitHubConnector[]>("/api/v1/github/connectors"),

  createGitHubConnector: (payload: {
    name: string;
    mode: ScmMode;
    auth_type: ScmAuthType;
    github_app_id?: string;
    github_installation_id?: string;
    credential?: string;
    service_repo_map: Record<string, string>;
  }) =>
    apiFetch<GitHubConnector>("/api/v1/github/connectors", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  testGitHubConnector: (id: number) =>
    apiFetch<GitHubConnectionTest>(`/api/v1/github/connectors/${id}/test`, { method: "POST" }),

  correlateGitHub: (incidentId: number, lookback_hours = 24) =>
    apiFetch<CorrelateGitHubResponse>(`/api/v1/incidents/${incidentId}/correlate-github`, {
      method: "POST",
      body: JSON.stringify({ lookback_hours }),
    }),

  searchLogs: (params: {
    service?: string;
    severity?: LogSeverity | "";
    environment?: string;
    correlation_id?: string;
    trace_id?: string;
    q?: string;
    limit?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.service) qs.set("service", params.service);
    if (params.severity) qs.set("severity", params.severity);
    if (params.environment) qs.set("environment", params.environment);
    if (params.correlation_id) qs.set("correlation_id", params.correlation_id);
    if (params.trace_id) qs.set("trace_id", params.trace_id);
    if (params.q) qs.set("q", params.q);
    if (params.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return apiFetch<LogSearchResponse>(`/api/v1/evidence/logs${q ? `?${q}` : ""}`);
  },

  loadSyntheticLogs: () =>
    apiFetch<{ ingested_count: number; is_synthetic: boolean }>("/api/v1/evidence/logs/load-fixtures", {
      method: "POST",
    }),

  listKnowledgeDocuments: () =>
    apiFetch<{ items: KnowledgeDocument[]; total: number }>("/api/v1/evidence/kb/documents"),

  uploadKnowledgeDocument: (payload: {
    title: string;
    filename: string;
    mime_type: string;
    content: string;
    source_uri?: string;
  }) =>
    apiFetch<KnowledgeDocument>("/api/v1/evidence/kb/documents", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  loadSyntheticRunbooks: () =>
    apiFetch<{ items: KnowledgeDocument[]; total: number }>("/api/v1/evidence/kb/load-fixtures", {
      method: "POST",
    }),

  reindexKnowledgeDocument: (docId: number) =>
    apiFetch<KnowledgeDocument>(`/api/v1/evidence/kb/documents/${docId}/reindex`, {
      method: "POST",
    }),

  deleteKnowledgeDocument: (docId: number) =>
    apiFetch<void>(`/api/v1/evidence/kb/documents/${docId}`, {
      method: "DELETE",
    }),

  searchKnowledgeBase: (query: string, limit = 5, service_hint?: string) =>
    apiFetch<KnowledgeSearchResponse>("/api/v1/evidence/kb/search", {
      method: "POST",
      body: JSON.stringify({ query, limit, ...(service_hint ? { service_hint } : {}) }),
    }),

  getIncidentEvidenceContext: (incidentId: number) =>
    apiFetch<IncidentEvidenceContext>(`/api/v1/evidence/incidents/${incidentId}/context`),

  getAIStatus: () => apiFetch<AIStatus>("/api/v1/ai/status"),

  listIncidentInvestigations: (incidentId: number) =>
    apiFetch<InvestigationRun[]>(`/api/v1/incidents/${incidentId}/investigations`),

  startInvestigation: (incidentId: number, window_hours = 24) =>
    apiFetch<InvestigationRun>(`/api/v1/incidents/${incidentId}/investigations`, {
      method: "POST",
      body: JSON.stringify({ window_hours }),
    }),

  cancelInvestigation: (investigationId: number) =>
    apiFetch<InvestigationRun>(`/api/v1/investigations/${investigationId}/cancel`, {
      method: "POST",
    }),

  submitInvestigationFeedback: (
    investigationId: number,
    rating: "helpful" | "not_helpful" | "inaccurate",
    note?: string,
  ) =>
    apiFetch<InvestigationRun>(`/api/v1/investigations/${investigationId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ rating, ...(note ? { note } : {}) }),
    }),

  listActionConnectors: () => apiFetch<ActionConnector[]>("/api/v1/action-connectors"),

  createActionConnector: (payload: {
    provider: ActionProviderType;
    name: string;
    mode: "mock" | "live";
    base_url?: string;
    allowed_targets: string[];
    credential?: string;
  }) =>
    apiFetch<ActionConnector>("/api/v1/action-connectors", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  testActionConnector: (connectorId: number) =>
    apiFetch<ActionConnectorTest>(`/api/v1/action-connectors/${connectorId}/test`, {
      method: "POST",
    }),

  listActions: (status?: ProposedActionStatus | "") =>
    apiFetch<ProposedAction[]>(`/api/v1/actions${status ? `?status=${status}` : ""}`),

  listIncidentActions: (incidentId: number) =>
    apiFetch<ProposedAction[]>(`/api/v1/incidents/${incidentId}/actions`),

  proposeAction: (
    incidentId: number,
    payload: {
      connector_id: number;
      action_type: ActionType;
      target_destination: string;
      payload: Record<string, unknown>;
      evidence_links?: string[];
    },
  ) =>
    apiFetch<ProposedAction>(`/api/v1/incidents/${incidentId}/actions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  approveAction: (actionId: number) =>
    apiFetch<ProposedAction>(`/api/v1/actions/${actionId}/approve`, { method: "POST" }),

  rejectAction: (actionId: number, reason: string) =>
    apiFetch<ProposedAction>(`/api/v1/actions/${actionId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  executeAction: (actionId: number) =>
    apiFetch<ProposedAction>(`/api/v1/actions/${actionId}/execute`, { method: "POST" }),
};
