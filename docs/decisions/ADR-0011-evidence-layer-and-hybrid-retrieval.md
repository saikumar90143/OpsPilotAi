# ADR-0011: Evidence Layer — Structured Logs, Knowledge Base & Hybrid Retrieval

- **Status:** Accepted (Phase 7)
- **Date:** 2026-11-21

## Context

Phase 8 will introduce an AI investigation workflow that needs trustworthy, tenant-scoped evidence:
1. Structured application logs with secret/PII redaction and bounded query semantics.
2. An engineering knowledge base (runbooks, postmortems) with stable citations and prompt-injection awareness.

## Decisions

1. **Structured Log Ingestion & Bounded Search (`application_logs`)**
   - All timestamps are normalized to UTC on ingestion.
   - Secrets (`Bearer` tokens, `DATABASE_URL` passwords, GitHub/AWS/OpenAI keys, JWTs, sensitive keys) and PII (emails, SSNs, card-like digits) are deterministically redacted via `app/core/redaction.py` before persistence.
   - Queries are strictly tenant-scoped (`organization_id`) and bounded to a configurable UTC time window (`LOG_QUERY_MAX_WINDOW_HOURS = 168`, `limit <= 100`). Unrestricted arbitrary queries or filesystem log access are prohibited.
   - Synthetic demo logs (`app/fixtures/demo_logs.jsonl`) are explicitly marked `is_synthetic=True` and `source="synthetic_fixture"`.

2. **Knowledge Base Format & Upload Safety (`knowledge_documents`, `knowledge_chunks`)**
   - Phase 7 supports UTF-8 Markdown (`.md`) and plain text (`.txt`) only. PDF is deferred until a reliable page/section citation parser is warranted.
   - Uploads undergo filename sanitization, MIME/extension allowlist checking, size limits (`KB_MAX_UPLOAD_BYTES = 524_288`), NUL-byte rejection, UTF-8 decoding verification, and binary magic-byte checks (`MZ`, `\x7fELF`, `%PDF-`, `PK\x03\x04`).
   - **Malware Scan Limitation:** Local checks provide structural/type safety only; no external AV daemon (e.g., ClamAV) is bundled in Phase 7.
   - Re-uploading to the same `(organization_id, source_uri)` auto-increments `version` and records SHA-256 `content_hash`.

3. **Hybrid Retrieval & Untrusted Content Boundary**
   - Chunks are created with Markdown heading awareness (`section_heading`, `chunk_index`, `char_start`, `char_end`).
   - Retrieval combines lexical scoring and a deterministic offline 128-dimensional L2-normalized n-gram hash embedding (`embedding_json` cosine similarity) via weighted fusion (`0.55 * lexical + 0.45 * semantic`). This avoids external embedding API dependencies in local/CI runs while keeping the schema ready for `pgvector` in production.
   - Every search response includes `untrusted_content: true`, a `trust_boundary` notice, and `injection_warning` flagging for common instruction-override phrases.

## Consequences

- Future Phase 8 AI tools can retrieve logs and runbook citations without cross-tenant leakage or secret exposure.
- Upgrading `embedding_json` to `pgvector` `vector(128)` (or external embeddings) is additive and preserves the public API contract.
