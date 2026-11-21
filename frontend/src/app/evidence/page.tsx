"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { EmptyState, ErrorAlert, LoadingSkeleton } from "@/components/Feedback";
import { ApiClientError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  ApplicationLogEntry,
  KnowledgeDocument,
  KnowledgeSearchResponse,
  LogSeverity,
} from "@/lib/types";

export default function EvidencePage() {
  const { session } = useAuth();
  const [tab, setTab] = useState<"logs" | "kb">("logs");

  // Logs state
  const [logs, setLogs] = useState<ApplicationLogEntry[]>([]);
  const [logsTotal, setLogsTotal] = useState(0);
  const [logsLoading, setLogsLoading] = useState(true);
  const [logsError, setLogsError] = useState<string | null>(null);
  const [serviceFilter, setServiceFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState<LogSeverity | "">("");
  const [traceFilter, setTraceFilter] = useState("");
  const [logQuery, setLogQuery] = useState("");

  // KB state
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [kbLoading, setKbLoading] = useState(true);
  const [kbError, setKbError] = useState<string | null>(null);
  const [kbSearchQuery, setKbSearchQuery] = useState("");
  const [kbSearchResult, setKbSearchResult] = useState<KnowledgeSearchResponse | null>(null);

  // Upload form
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFilename, setUploadFilename] = useState("");
  const [uploadMime, setUploadMime] = useState("text/markdown");
  const [uploadContent, setUploadContent] = useState("");
  const [busy, setBusy] = useState(false);

  const canWriteLogs =
    session?.role === "owner" ||
    session?.role === "admin" ||
    session?.role === "engineer";
  const canManageKb = session?.role === "owner" || session?.role === "admin";

  const fetchLogs = useCallback(async () => {
    setLogsLoading(true);
    setLogsError(null);
    try {
      const res = await api.searchLogs({
        service: serviceFilter || undefined,
        severity: severityFilter,
        trace_id: traceFilter || undefined,
        q: logQuery || undefined,
        limit: 50,
      });
      setLogs(res.items);
      setLogsTotal(res.total);
    } catch (err) {
      setLogsError(err instanceof ApiClientError ? err.message : "Failed to load logs");
    } finally {
      setLogsLoading(false);
    }
  }, [serviceFilter, severityFilter, traceFilter, logQuery]);

  const fetchDocs = useCallback(async () => {
    setKbLoading(true);
    setKbError(null);
    try {
      const res = await api.listKnowledgeDocuments();
      setDocs(res.items);
    } catch (err) {
      setKbError(
        err instanceof ApiClientError ? err.message : "Failed to load knowledge documents",
      );
    } finally {
      setKbLoading(false);
    }
  }, []);

  useEffect(() => {
    if (session) {
      void fetchLogs();
      void fetchDocs();
    }
  }, [session, fetchLogs, fetchDocs]);

  const handleLoadDemoLogs = async () => {
    setBusy(true);
    setLogsError(null);
    try {
      await api.loadSyntheticLogs();
      await fetchLogs();
    } catch (err) {
      setLogsError(err instanceof ApiClientError ? err.message : "Failed to load synthetic logs");
    } finally {
      setBusy(false);
    }
  };

  const handleLoadDemoRunbooks = async () => {
    setBusy(true);
    setKbError(null);
    try {
      await api.loadSyntheticRunbooks();
      await fetchDocs();
    } catch (err) {
      setKbError(
        err instanceof ApiClientError ? err.message : "Failed to load synthetic runbooks",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadFilename(file.name);
    if (!uploadTitle) {
      setUploadTitle(file.name.replace(/\.(md|txt)$/i, ""));
    }
    setUploadMime(file.name.toLowerCase().endsWith(".md") ? "text/markdown" : "text/plain");
    const text = await file.text();
    setUploadContent(text);
  };

  const handleUploadDoc = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setKbError(null);
    try {
      await api.uploadKnowledgeDocument({
        title: uploadTitle.trim(),
        filename: uploadFilename.trim(),
        mime_type: uploadMime,
        content: uploadContent,
      });
      setUploadTitle("");
      setUploadFilename("");
      setUploadContent("");
      await fetchDocs();
    } catch (err) {
      setKbError(err instanceof ApiClientError ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const handleSearchKb = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!kbSearchQuery.trim()) return;
    setBusy(true);
    setKbError(null);
    try {
      const res = await api.searchKnowledgeBase(kbSearchQuery.trim(), 5);
      setKbSearchResult(res);
    } catch (err) {
      setKbError(err instanceof ApiClientError ? err.message : "Knowledge search failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">
              Evidence &amp; Engineering Knowledge Base
            </h1>
            <p className="text-sm text-slate-600">
              Bounded structured log search (with secret/PII redaction) and tenant-scoped runbook
              retrieval.
            </p>
          </div>
          <div className="flex rounded-md border border-slate-300 bg-white p-0.5 text-xs font-medium">
            <button
              type="button"
              onClick={() => setTab("logs")}
              className={`rounded px-3 py-1.5 ${
                tab === "logs" ? "bg-indigo-600 text-white" : "text-slate-700 hover:bg-slate-50"
              }`}
            >
              Structured Logs ({logsTotal})
            </button>
            <button
              type="button"
              onClick={() => setTab("kb")}
              className={`rounded px-3 py-1.5 ${
                tab === "kb" ? "bg-indigo-600 text-white" : "text-slate-700 hover:bg-slate-50"
              }`}
            >
              Knowledge Base ({docs.length})
            </button>
          </div>
        </div>

        {tab === "logs" ? (
          <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap gap-2">
                <input
                  type="text"
                  placeholder="Service (e.g. checkout-api)"
                  value={serviceFilter}
                  onChange={(e) => setServiceFilter(e.target.value)}
                  className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs"
                />
                <select
                  aria-label="Severity filter"
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value as LogSeverity | "")}
                  className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
                >
                  <option value="">All severities</option>
                  <option value="DEBUG">DEBUG</option>
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
                <input
                  type="text"
                  placeholder="Trace ID"
                  value={traceFilter}
                  onChange={(e) => setTraceFilter(e.target.value)}
                  className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs"
                />
                <input
                  type="text"
                  placeholder="Message contains..."
                  value={logQuery}
                  onChange={(e) => setLogQuery(e.target.value)}
                  className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs"
                />
              </div>

              <button
                type="button"
                disabled={!canWriteLogs || busy}
                onClick={handleLoadDemoLogs}
                className="rounded-md border border-violet-300 bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-800 hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Load Synthetic Demo Logs
              </button>
            </div>

            {logsError && <ErrorAlert error={logsError} />}

            {logsLoading ? (
              <LoadingSkeleton rows={4} />
            ) : logs.length === 0 ? (
              <EmptyState
                title="No logs in bounded 24h window"
                description="Ingest structured logs or load the synthetic demo log fixtures."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="py-2 pr-3">Time (UTC)</th>
                      <th className="py-2 pr-3">Service</th>
                      <th className="py-2 pr-3">Severity</th>
                      <th className="py-2 pr-3">Trace / Corr</th>
                      <th className="py-2 pr-3">Message</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {logs.map((log) => (
                      <tr key={log.id} className="align-top">
                        <td className="whitespace-nowrap py-2 pr-3 font-mono text-[11px] text-slate-500">
                          {new Date(log.timestamp).toISOString().replace("T", " ").slice(0, 19)}
                        </td>
                        <td className="whitespace-nowrap py-2 pr-3 font-medium text-slate-800">
                          {log.service}
                          <div className="text-[10px] text-slate-400">{log.environment}</div>
                        </td>
                        <td className="whitespace-nowrap py-2 pr-3">
                          <span
                            className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ${
                              log.severity === "ERROR" || log.severity === "CRITICAL"
                                ? "bg-rose-100 text-rose-800"
                                : log.severity === "WARNING"
                                  ? "bg-amber-100 text-amber-800"
                                  : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {log.severity}
                          </span>
                          {log.is_synthetic && (
                            <span className="ml-1 rounded bg-violet-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-violet-800">
                              SYNTHETIC
                            </span>
                          )}
                        </td>
                        <td className="whitespace-nowrap py-2 pr-3 font-mono text-[11px] text-slate-500">
                          <div>{log.trace_id ?? "—"}</div>
                          <div>{log.correlation_id ?? "—"}</div>
                        </td>
                        <td className="py-2 pr-3 text-slate-700">
                          <p>{log.message}</p>
                          {Object.keys(log.attributes_json).length > 0 && (
                            <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-1.5 font-mono text-[10px] text-slate-600">
                              {JSON.stringify(log.attributes_json)}
                            </pre>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ) : (
          <div className="space-y-6">
            {/* Hybrid Search */}
            <section className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">
                Hybrid Knowledge Base Search
              </h2>
              <p className="mt-0.5 text-xs text-slate-600">
                Combines lexical matching and local semantic similarity with stable citations.
              </p>
              <form onSubmit={handleSearchKb} className="mt-3 flex gap-2">
                <input
                  type="text"
                  required
                  minLength={2}
                  placeholder="Search runbooks (e.g. POOL_EXHAUSTED checkout-api)"
                  value={kbSearchQuery}
                  onChange={(e) => setKbSearchQuery(e.target.value)}
                  className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                />
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-md bg-indigo-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  Search
                </button>
              </form>

              {kbSearchResult && (
                <div className="mt-4 space-y-3">
                  <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                    <strong>Trust Boundary:</strong> {kbSearchResult.trust_boundary}
                  </div>
                  {kbSearchResult.hits.length === 0 ? (
                    <EmptyState
                      title="No matching passages"
                      description="Upload a Markdown/text runbook or load synthetic runbooks below."
                    />
                  ) : (
                    <ul className="space-y-2.5">
                      {kbSearchResult.hits.map((hit) => (
                        <li
                          key={hit.chunk_id}
                          className="rounded-md border border-slate-200 p-3 text-xs"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="font-semibold text-slate-900">
                                {hit.document_title}
                              </span>
                              <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-700">
                                v{hit.version} · chunk #{hit.chunk_index}
                              </span>
                              {hit.is_synthetic && (
                                <span className="rounded bg-violet-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-violet-800">
                                  SYNTHETIC
                                </span>
                              )}
                              {hit.injection_warning && (
                                <span className="rounded bg-rose-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-rose-800">
                                  INJECTION PATTERN FLAGGED
                                </span>
                              )}
                            </div>
                            <span className="font-mono text-[11px] text-indigo-700">
                              score {hit.hybrid_score.toFixed(2)} (lex {hit.lexical_score.toFixed(2)}{" "}
                              / sem {hit.semantic_score.toFixed(2)})
                            </span>
                          </div>
                          <p className="mt-1 font-mono text-[11px] text-slate-500">
                            {hit.source_uri}
                            {hit.section_heading ? ` § ${hit.section_heading}` : ""} (chars{" "}
                            {hit.char_start}–{hit.char_end})
                          </p>
                          <p className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-2 text-slate-700">
                            {hit.snippet}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </section>

            {/* Documents & Upload */}
            <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">Runbook Documents</h2>
                  <p className="text-xs text-slate-500">
                    Markdown (.md) and plain text (.txt) only. Local MIME/UTF-8/magic-byte checks
                    active; no external AV daemon bundled.
                  </p>
                </div>
                <button
                  type="button"
                  disabled={!canManageKb || busy}
                  onClick={handleLoadDemoRunbooks}
                  className="rounded-md border border-violet-300 bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-800 hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Load Synthetic Runbooks
                </button>
              </div>

              {kbError && <ErrorAlert error={kbError} />}

              {kbLoading ? (
                <LoadingSkeleton rows={3} />
              ) : docs.length === 0 ? (
                <EmptyState
                  title="No knowledge documents"
                  description="Upload a Markdown/text runbook or load synthetic demo runbooks."
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-slate-200 text-slate-500">
                      <tr>
                        <th className="py-2 pr-3">Title &amp; Source URI</th>
                        <th className="py-2 pr-3">Version</th>
                        <th className="py-2 pr-3">Status</th>
                        <th className="py-2 pr-3">Chunks</th>
                        <th className="py-2 pr-3">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {docs.map((doc) => (
                        <tr key={doc.id}>
                          <td className="py-2 pr-3">
                            <div className="flex items-center gap-1.5 font-medium text-slate-900">
                              <span>{doc.title}</span>
                              {doc.is_synthetic && (
                                <span className="rounded bg-violet-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-violet-800">
                                  SYNTHETIC
                                </span>
                              )}
                            </div>
                            <div className="font-mono text-[11px] text-slate-500">
                              {doc.source_uri} · sha256:{doc.content_hash.slice(0, 12)}
                            </div>
                          </td>
                          <td className="py-2 pr-3 font-mono">v{doc.version}</td>
                          <td className="py-2 pr-3">
                            <span
                              className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ${
                                doc.indexing_status === "indexed"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : doc.indexing_status === "failed"
                                    ? "bg-rose-100 text-rose-800"
                                    : "bg-amber-100 text-amber-800"
                              }`}
                            >
                              {doc.indexing_status.toUpperCase()}
                            </span>
                          </td>
                          <td className="py-2 pr-3 font-mono">{doc.chunk_count}</td>
                          <td className="py-2 pr-3">
                            <div className="flex gap-2">
                              <button
                                type="button"
                                disabled={!canManageKb || busy}
                                onClick={async () => {
                                  setBusy(true);
                                  try {
                                    await api.reindexKnowledgeDocument(doc.id);
                                    await fetchDocs();
                                  } finally {
                                    setBusy(false);
                                  }
                                }}
                                className="rounded border border-slate-300 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                              >
                                Re-index
                              </button>
                              <button
                                type="button"
                                disabled={!canManageKb || busy}
                                onClick={async () => {
                                  setBusy(true);
                                  try {
                                    await api.deleteKnowledgeDocument(doc.id);
                                    await fetchDocs();
                                  } finally {
                                    setBusy(false);
                                  }
                                }}
                                className="rounded border border-rose-200 px-2 py-1 text-[11px] text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                              >
                                Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {canManageKb && (
                <form
                  onSubmit={handleUploadDoc}
                  className="space-y-3 border-t border-slate-100 pt-4 text-xs"
                >
                  <p className="font-semibold text-slate-800">Upload Markdown / Text Runbook</p>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <input
                      type="text"
                      required
                      placeholder="Document title"
                      value={uploadTitle}
                      onChange={(e) => setUploadTitle(e.target.value)}
                      className="rounded-md border border-slate-300 px-2.5 py-1.5"
                    />
                    <input
                      type="text"
                      required
                      placeholder="Filename (e.g. redis-runbook.md)"
                      value={uploadFilename}
                      onChange={(e) => setUploadFilename(e.target.value)}
                      className="rounded-md border border-slate-300 px-2.5 py-1.5"
                    />
                    <input
                      type="file"
                      accept=".md,.txt,text/markdown,text/plain"
                      onChange={handleFileSelect}
                      className="text-slate-600"
                    />
                  </div>
                  <textarea
                    required
                    rows={4}
                    placeholder="# Heading&#10;Paste Markdown or plain text runbook content..."
                    value={uploadContent}
                    onChange={(e) => setUploadContent(e.target.value)}
                    className="w-full rounded-md border border-slate-300 p-2.5 font-mono text-xs"
                  />
                  <button
                    type="submit"
                    disabled={busy}
                    className="rounded-md bg-indigo-600 px-4 py-1.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                  >
                    Upload &amp; Index Document
                  </button>
                </form>
              )}
            </section>
          </div>
        )}
      </div>
    </AppShell>
  );
}
