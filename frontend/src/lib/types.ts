export type Role = "owner" | "admin" | "engineer" | "viewer";

export type Severity = "critical" | "high" | "medium" | "low";

export type IncidentStatus =
  | "open"
  | "acknowledged"
  | "investigating"
  | "resolved"
  | "closed";

export type Environment = "production" | "staging" | "development" | "unknown";

export type EvidenceKind = "log" | "metric" | "trace" | "commit" | "runbook" | "link";

export type InboundEventStatus =
  | "received"
  | "queued"
  | "processing"
  | "processed"
  | "retrying"
  | "dead_letter";

export type ConnectionStatus = "simulator" | "configured" | "disabled";

export interface ApiErrorBody {
  error: string;
  message: string;
  request_id: string;
  details?: Array<{ loc: Array<string | number>; msg: string; type: string }>;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface Organization {
  id: number;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
}

export interface AuthSession {
  user: User;
  organization: Organization;
  role: Role;
}

export interface Membership {
  id: number;
  organization_id: number;
  user_id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface Incident {
  id: number;
  organization_id: number;
  created_by_user_id: number | null;
  assignee_user_id: number | null;
  title: string;
  description: string;
  service: string;
  environment: Environment;
  severity: Severity;
  status: IncidentStatus;
  source: string;
  external_source_id: string | null;
  fingerprint: string | null;
  metadata: Record<string, unknown>;
  version: number;
  affected_services: string[];
  tags: string[];
  acknowledged_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimelineEvent {
  id: number;
  organization_id: number;
  incident_id: number;
  actor_user_id: number | null;
  event_type: string;
  message: string;
  details_json: Record<string, unknown>;
  created_at: string;
}

export interface Comment {
  id: number;
  organization_id: number;
  incident_id: number;
  author_user_id: number;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface EvidenceRef {
  id: number;
  organization_id: number;
  incident_id: number;
  added_by_user_id: number | null;
  kind: EvidenceKind;
  title: string;
  uri: string | null;
  summary: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface Integration {
  id: number;
  organization_id: number;
  provider: "alertmanager";
  name: string;
  is_enabled: boolean;
  is_simulator_mode: boolean;
  connection_status: ConnectionStatus;
  webhook_path: string;
  secret_rotated_at: string | null;
  rotation_grace_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface IntegrationCreated extends Integration {
  signing_secret: string;
}

export interface SecretRotated {
  integration_id: number;
  signing_secret: string;
  rotation_grace_until: string;
}

export interface InboundEvent {
  id: number;
  organization_id: number;
  integration_id: number;
  provider: string;
  idempotency_key: string;
  provider_event_id: string;
  fingerprint: string;
  is_simulated: boolean;
  status: InboundEventStatus;
  attempt_count: number;
  max_attempts: number;
  last_error: string | null;
  correlation_id: string;
  incident_id: number | null;
  normalized_payload_json: Record<string, unknown>;
  received_at: string;
  processed_at: string | null;
  next_retry_at: string | null;
  dead_lettered_at: string | null;
  updated_at: string;
}

export type ScmMode = "mock" | "live";
export type ScmAuthType = "mock" | "github_app" | "pat";

export interface GitHubConnector {
  id: number;
  organization_id: number;
  name: string;
  mode: ScmMode;
  auth_type: ScmAuthType;
  github_app_id: string | null;
  github_installation_id: string | null;
  has_credential: boolean;
  has_webhook_secret: boolean;
  webhook_path: string;
  service_repo_map: Record<string, string>;
  is_enabled: boolean;
  last_test_status: string;
  last_test_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  permission_summary: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface GitHubConnectionTest {
  ok: boolean;
  mode: ScmMode;
  permission_summary: Record<string, string>;
  rate_limit_remaining: number | null;
  diagnostics: string;
}

export interface CorrelateGitHubResponse {
  mode: ScmMode;
  repository: string;
  disclaimer: string;
  window_start: string;
  window_end: string;
  evidence_items: EvidenceRef[];
}

export interface AuditLog {
  id: number;
  organization_id: number | null;
  actor_user_id: number | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  request_id: string;
  ip_address: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export type LogSeverity = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

export interface ApplicationLogEntry {
  id: number;
  organization_id: number;
  service: string;
  environment: string;
  severity: LogSeverity;
  timestamp: string;
  correlation_id: string | null;
  trace_id: string | null;
  message: string;
  attributes_json: Record<string, unknown>;
  source: string;
  is_synthetic: boolean;
  created_at: string;
}

export interface LogSearchResponse {
  items: ApplicationLogEntry[];
  total: number;
  start_time: string;
  end_time: string;
  has_synthetic: boolean;
}

export interface KnowledgeDocument {
  id: number;
  organization_id: number;
  created_by_user_id: number | null;
  title: string;
  sanitized_filename: string;
  source_uri: string;
  source_type: string;
  mime_type: string;
  version: number;
  content_hash: string;
  byte_size: number;
  is_synthetic: boolean;
  indexing_status: "pending" | "indexing" | "indexed" | "failed";
  chunk_count: number;
  indexing_attempts: number;
  last_error: string | null;
  indexed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeSearchHit {
  document_id: number;
  document_title: string;
  source_uri: string;
  version: number;
  chunk_id: number;
  chunk_index: number;
  section_heading: string | null;
  char_start: number;
  char_end: number;
  lexical_score: number;
  semantic_score: number;
  hybrid_score: number;
  snippet: string;
  is_synthetic: boolean;
  untrusted_content: boolean;
  injection_warning: boolean;
}

export interface KnowledgeSearchResponse {
  query: string;
  trust_boundary: string;
  hits: KnowledgeSearchHit[];
}

export interface IncidentEvidenceContext {
  incident_id: number;
  title: string;
  affected_service: string | null;
  environment: string;
  severity: string;
  window_start: string;
  window_end: string;
  logs: ApplicationLogEntry[];
  knowledge_hits: KnowledgeSearchHit[];
  trust_boundary: string;
}

export interface AIStatus {
  provider_mode: "mock" | "openai";
  model_name: string;
  configured: boolean;
  prompt_version: string;
  max_graph_steps: number;
  max_tool_calls: number;
  tenant_daily_used: number;
  tenant_daily_quota: number;
  notice: string;
}

export interface InvestigationToolCall {
  id: number;
  step_number: number;
  tool_name: string;
  status: string;
  input_summary_json: Record<string, unknown>;
  output_count: number;
  latency_ms: number;
  error_message: string | null;
  created_at: string;
}

export interface EvidenceBundleItem {
  evidence_id: string;
  source_type: "incident" | "log" | "github" | "knowledge_base";
  title: string;
  timestamp: string | null;
  url_or_uri: string | null;
  summary: string;
  is_synthetic: boolean;
  untrusted_content: boolean;
}

export interface InvestigationReport {
  summary: string;
  insufficient_evidence: boolean;
  conflicting_evidence: boolean;
  observed_facts: Array<{ statement: string; evidence_ids: string[] }>;
  possible_causes: Array<{
    hypothesis: string;
    confidence: "high" | "medium" | "low";
    rationale: string;
    evidence_ids: string[];
  }>;
  missing_information: string[];
  recommended_diagnostics: string[];
  citations: string[];
}

export interface InvestigationRun {
  id: number;
  organization_id: number;
  incident_id: number;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  provider_mode: "mock" | "openai";
  model_name: string;
  prompt_version: string;
  window_hours: number;
  graph_steps: number;
  tool_calls_count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
  latency_ms: number;
  evidence_bundle_json: EvidenceBundleItem[];
  report_json: InvestigationReport | null;
  error_message: string | null;
  human_feedback_rating: "helpful" | "not_helpful" | "inaccurate" | null;
  human_feedback_note: string | null;
  created_at: string;
  completed_at: string | null;
  tool_calls: InvestigationToolCall[];
}

export type ActionProviderType = "jira" | "slack";
export type ActionType = "jira_create_issue" | "slack_post_message";
export type ProposedActionStatus =
  | "proposed"
  | "approved"
  | "executing"
  | "succeeded"
  | "failed"
  | "rejected"
  | "expired";

export interface ActionConnector {
  id: number;
  organization_id: number;
  provider: ActionProviderType;
  name: string;
  mode: "mock" | "live";
  base_url: string | null;
  allowed_targets_json: string[];
  has_credential: boolean;
  permission_summary_json: Record<string, string>;
  last_test_status: string;
  last_test_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ActionConnectorTest {
  ok: boolean;
  mode: string;
  permission_summary: Record<string, string>;
  diagnostics: string;
}

export interface ProposedAction {
  id: number;
  organization_id: number;
  incident_id: number;
  investigation_id: number | null;
  connector_id: number;
  connector_mode: "mock" | "live";
  action_type: ActionType;
  target_system: ActionProviderType;
  target_destination: string;
  payload_preview_json: Record<string, unknown>;
  payload_hash: string;
  evidence_links_json: string[];
  requested_by_type: "user" | "ai";
  requested_by_user_id: number | null;
  status: ProposedActionStatus;
  approved_by_user_id: number | null;
  approved_at: string | null;
  rejected_by_user_id: number | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  expires_at: string;
  idempotency_key: string;
  execution_attempts: number;
  external_id: string | null;
  external_url: string | null;
  execution_result_json: Record<string, unknown> | null;
  last_error: string | null;
  executed_at: string | null;
  created_at: string;
  updated_at: string;
}
