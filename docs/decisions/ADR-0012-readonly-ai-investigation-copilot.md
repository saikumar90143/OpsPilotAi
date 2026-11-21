# ADR-0012: Read-Only AI Investigation Copilot (OpenAI Responses API & Bounded LangGraph)

- **Status:** Accepted (Phase 8)
- **Date:** 2026-11-21

## Context

Phase 8 introduces an AI investigation copilot for incidents without permitting any external write actions (which are gated behind human approval in Phase 9).

## Decisions

1. **Official OpenAI Responses API & Configurable Model**
   - Uses `openai.OpenAI` with `client.responses.parse(..., text_format=InvestigationReport)` for structured output. The retired Assistants API is never used.
   - `OPENAI_MODEL` is environment-configured (never hard-coded to an unavailable model) and validated via `client.models.retrieve(...)` on first use with graceful `ServiceUnavailableError` mapping.
   - `AI_PROVIDER_MODE=mock` provides a deterministic offline `MockInvestigationModel` for tests, CI, and credential-free demos.

2. **Bounded LangGraph State Machine**
   - Uses `langgraph.graph.StateGraph` solely for a 4-step bounded workflow (`validate_and_load` → `collect_evidence` → `synthesize_report` → `validate_citations`) with `recursion_limit = AI_MAX_GRAPH_STEPS`.
   - Domain logic, RBAC, and persistence remain in ordinary Python services (`investigation_service.py`) and typed tools (`app/ai/tools.py`).

3. **Fixed Allowlist of Read-Only Tools & Security Guardrails**
   - Only 4 read-only, tenant-scoped, time-bounded tools are exposed (`get_incident_history`, `search_service_logs`, `correlate_github_evidence`, `search_knowledge_base`).
   - No arbitrary SQL, shell access, unrestricted HTTP, credentials, or write operations are exposed.
   - Every tool executes with a per-tool timeout (`AI_TOOL_TIMEOUT_SECONDS`), tool-call cap (`AI_MAX_TOOL_CALLS`), and secret/PII redaction.

4. **Strict Citation Validation & Prompt-Injection Isolation**
   - Every retrieved evidence item is assigned a deterministic `evidence_id` (`EV-INC-*`, `EV-LOG-*`, `EV-GH-*`, `EV-KB-*`) and marked `untrusted_content: true`.
   - `validate_report_citations` rejects any report citing an unknown or fabricated `evidence_id`, transitioning the run to `failed` rather than persisting ungrounded claims.

5. **Usage Controls & Traceability**
   - Enforces per-user sliding-window rate limits (`AI_RATE_LIMIT_REQUESTS`) and per-tenant 24h quotas (`AI_TENANT_DAILY_QUOTA`).
   - Persists `InvestigationRun` and `InvestigationToolCall` records (model/prompt version, tokens, latency, status, human feedback) and `AuditLog` entries.
