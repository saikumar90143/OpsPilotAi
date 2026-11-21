# OpsPilot AI — Engineering Case Study

## 1. Customer Problem & Constraints
On-call engineers investigating production incidents waste critical minutes jumping between alert managers, raw logs, GitHub commits, and scattered runbooks—while unguarded AI copilots risk hallucinating root causes, leaking secrets, or executing destructive actions.

**Key Constraints:**
- Strict multi-tenant isolation (zero cross-tenant data leakage).
- Zero autonomous external writes (Jira/Slack writes require explicit human approval).
- Full offline testability without paid OpenAI or external SaaS credentials.

---

## 2. Architecture & Key Trade-Offs
- **Modular Monolith + Celery Worker:** FastAPI handles synchronous auth, RBAC, and bounded queries; Celery + Redis processes inbound webhooks asynchronously after PostgreSQL persistence (`inbound_events`), preventing event loss if Redis restarts.
- **Direct SQLAlchemy Services over Heavy Repositories:** Domain logic lives in focused service modules (`incidents.py`, `ingestion_service.py`, `evidence_service.py`, `investigation_service.py`, `action_service.py`) rather than generic repository wrappers.
- **Offline Hybrid Retrieval:** Combines lexical scoring with deterministic 128-dim L2-normalized n-gram hash embeddings (`embedding_json`), avoiding external embedding API dependencies while keeping the schema ready for `pgvector`.
- **Bounded LangGraph State Machine:** LangGraph orchestrates only 4 explicit steps (`validate_and_load` → `collect_evidence` → `synthesize_report` → `validate_citations`) over a fixed allowlist of 4 read-only tools.

---

## 3. Security & Failure Handling
- **Auth & RBAC:** Argon2id hashing, `HttpOnly` JWT/refresh cookies with reuse-detection family revocation, double-submit CSRF, and server-side RBAC (`OWNER`/`ADMIN`/`ENGINEER`/`VIEWER`).
- **SSRF, Redaction & Untrusted Data:** Outbound connector URLs pass `validate_safe_outbound_url`; logs and errors pass `redact_text()`; retrieved evidence is framed as `untrusted_content=True`; `validate_report_citations()` rejects any fabricated `evidence_id`.
- **Human Approval Gate:** `ProposedAction` enforces destination allowlists, `payload_hash` integrity, separation of duties (`ACTION_ALLOW_SELF_APPROVAL=false`), expiry, execution-time DB membership re-verification, and idempotent retries.

---

## 4. Evaluation Methodology & Measured Results

### Offline AI Evaluation (`eval-dataset-v1.0`, `MockInvestigationModel`)
- **Total Cases:** 5 synthetic scenarios (corroborated DB pool exhaustion, payment timeout, sparse/no-data uncertainty, conflicting evidence, prompt injection).
- **Measured Results:**
  - `uncertainty_precision`: **1.0** | `uncertainty_recall`: **1.0** | `uncertainty_f1`: **1.0**
  - `citation_validity_rate`: **1.0** | `citation_coverage_rate`: **1.0**
  - `retrieval_relevance_rate`: **1.0** | `tool_selection_accuracy`: **1.0**
  - `unsupported_claim_rate`: **0.0** | `mean_latency_ms`: **30.6 ms**

### Baseline Load Measurements (`scripts/load_test.py`, Windows 10, Python 3.12.5, 4 CPUs, in-process ASGI + SQLite)
- `POST /api/v1/incidents` (50 reqs): **94.89 req/s** (`p50 8.69 ms`, `p95 9.78 ms`)
- `GET /api/v1/incidents?limit=20` (100 reqs): **108.61 req/s** (`p50 8.83 ms`, `p95 11.26 ms`)
- `POST /api/v1/webhooks/alertmanager` (50 reqs): **112.09 req/s** (`p50 7.84 ms`, `p95 10.18 ms`)
- `Worker execute_event_processing` (50 jobs): **278.19 jobs/s** (`p50 3.44 ms`, `p95 6.45 ms`)
- `POST /api/v1/incidents/1/investigations` (mock, 20 runs): **36.64 req/s** (`p50 25.23 ms`, `p95 31.22 ms`)
