"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { SeverityBadge, SimulatedBadge, StatusBadge } from "@/components/Badges";
import { EmptyState, ErrorAlert, LoadingSkeleton } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canTransition } from "@/lib/rbac";
import type {
  ActionConnector,
  AIStatus,
  AuditLog,
  Comment,
  EvidenceKind,
  EvidenceRef,
  Incident,
  IncidentEvidenceContext,
  IncidentStatus,
  InvestigationRun,
  Membership,
  ProposedAction,
  TimelineEvent,
} from "@/lib/types";

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { can } = useAuth();
  const incidentId = Number(params.id);

  const canWrite = can("incident:write");
  const canArchive = can("incident:archive");
  const canReadAudit = can("audit:read");

  const [incident, setIncident] = useState<Incident | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [comments, setComments] = useState<Comment[]>([]);
  const [evidence, setEvidence] = useState<EvidenceRef[]>([]);
  const [members, setMembers] = useState<Membership[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const [commentBody, setCommentBody] = useState("");
  const [evKind, setEvKind] = useState<EvidenceKind>("log");
  const [evTitle, setEvTitle] = useState("");
  const [evUri, setEvUri] = useState("");
  const [evSummary, setEvSummary] = useState("");
  const [ghDisclaimer, setGhDisclaimer] = useState<string | null>(null);
  const [evContext, setEvContext] = useState<IncidentEvidenceContext | null>(null);
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);
  const [investigations, setInvestigations] = useState<InvestigationRun[]>([]);
  const [feedbackNote, setFeedbackNote] = useState("");
  const [actionConnectors, setActionConnectors] = useState<ActionConnector[]>([]);
  const [proposedActions, setProposedActions] = useState<ProposedAction[]>([]);
  const [selectedConnId, setSelectedConnId] = useState<number | "">("");
  const [actDestination, setActDestination] = useState("");
  const [actSummary, setActSummary] = useState("");
  const [actBody, setActBody] = useState("");
  const [actRejectReason, setActRejectReason] = useState<Record<number, string>>({});

  const loadAll = useCallback(async () => {
    if (!Number.isFinite(incidentId)) return;
    setLoading(true);
    setError(null);
    try {
      const [inc, tl, cm, ev, mem, ctx, aiSt, invs, conns, acts] = await Promise.all([
        api.getIncident(incidentId),
        api.listTimeline(incidentId),
        api.listComments(incidentId),
        api.listEvidence(incidentId),
        api.listMemberships(),
        api.getIncidentEvidenceContext(incidentId).catch(() => null),
        api.getAIStatus().catch(() => null),
        api.listIncidentInvestigations(incidentId).catch(() => []),
        api.listActionConnectors().catch(() => []),
        api.listIncidentActions(incidentId).catch(() => []),
      ]);
      setIncident(inc);
      setTimeline(tl);
      setComments(cm);
      setEvidence(ev);
      setMembers(mem);
      setEvContext(ctx);
      setAiStatus(aiSt);
      setInvestigations(invs);
      setActionConnectors(conns);
      setProposedActions(acts);

      if (canReadAudit) {
        const logs = await api.listAuditLogs(100);
        setAuditLogs(
          logs.filter((l) => l.target_type === "incident" && l.target_id === String(incidentId)),
        );
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [incidentId, canReadAudit]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const runAction = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
      await loadAll();
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  };

  const handleLifecycle = (target: IncidentStatus) => {
    if (!incident) return;
    void runAction(async () => {
      if (target === "acknowledged") {
        await api.acknowledgeIncident(incident.id, incident.version);
      } else if (target === "resolved") {
        await api.resolveIncident(incident.id, incident.version);
      } else if (target === "open") {
        await api.reopenIncident(incident.id, incident.version);
      } else {
        await api.transitionIncidentStatus(incident.id, target, incident.version);
      }
    });
  };

  const handleAssign = (userIdRaw: string) => {
    if (!incident) return;
    const assigneeId = userIdRaw ? Number(userIdRaw) : null;
    void runAction(() => api.assignIncident(incident.id, assigneeId, incident.version));
  };

  const handleArchive = () => {
    if (!incident) return;
    void runAction(async () => {
      await api.archiveIncident(incident.id);
      router.replace("/incidents");
    });
  };

  const handleAddComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!incident || !commentBody.trim()) return;
    void runAction(async () => {
      await api.addComment(incident.id, commentBody.trim());
      setCommentBody("");
    });
  };

  const handleAddEvidence = (e: React.FormEvent) => {
    e.preventDefault();
    if (!incident || !evTitle.trim()) return;
    void runAction(async () => {
      await api.addEvidence(incident.id, {
        kind: evKind,
        title: evTitle.trim(),
        ...(evUri.trim() ? { uri: evUri.trim() } : {}),
        summary: evSummary.trim(),
      });
      setEvTitle("");
      setEvUri("");
      setEvSummary("");
    });
  };

  const memberName = (userId: number | null) => {
    if (userId === null) return "System";
    return members.find((m) => m.user_id === userId)?.full_name ?? `User #${userId}`;
  };

  return (
    <AppShell>
      <Link
        href="/incidents"
        className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
        <span>Back to incidents</span>
      </Link>

      {error !== null && (
        <div className="mt-4">
          <ErrorAlert error={error} onRetry={loadAll} />
        </div>
      )}

      {loading ? (
        <div className="mt-6">
          <LoadingSkeleton rows={5} />
        </div>
      ) : incident ? (
        <div className="mt-4 space-y-6">
          {/* Header & lifecycle controls */}
          <section className="rounded-lg border border-slate-200 bg-white p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-slate-400">#{incident.id}</span>
                  <SeverityBadge severity={incident.severity} />
                  <StatusBadge status={incident.status} />
                  {Boolean(incident.metadata?.simulated) && <SimulatedBadge />}
                  <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-600">
                    v{incident.version}
                  </span>
                </div>
                <h1 className="mt-2 text-xl font-semibold text-slate-900">{incident.title}</h1>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">
                  {incident.description || "No description provided."}
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {(
                  [
                    ["acknowledged", "Acknowledge"],
                    ["investigating", "Investigate"],
                    ["resolved", "Resolve"],
                    ["closed", "Close"],
                    ["open", "Reopen"],
                  ] as Array<[IncidentStatus, string]>
                ).map(([target, label]) => {
                  const allowedByState = canTransition(incident.status, target);
                  const enabled = canWrite && allowedByState && !busy;
                  const reason = !canWrite
                    ? "Requires Engineer, Admin, or Owner role"
                    : !allowedByState
                      ? `Cannot transition from ${incident.status} to ${target}`
                      : undefined;
                  return (
                    <button
                      key={target}
                      type="button"
                      disabled={!enabled}
                      title={reason}
                      onClick={() => handleLifecycle(target)}
                      className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {label}
                    </button>
                  );
                })}
                <button
                  type="button"
                  disabled={!canArchive || busy}
                  title={canArchive ? "Archive incident" : "Requires Admin or Owner role"}
                  onClick={handleArchive}
                  className="rounded-md border border-rose-300 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-800 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Archive
                </button>
              </div>
            </div>

            {actionError !== null && (
              <div className="mt-4">
                <ErrorAlert error={actionError} />
              </div>
            )}

            <dl className="mt-6 grid grid-cols-1 gap-4 border-t border-slate-100 pt-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="font-medium text-slate-500">Primary Service & Env</dt>
                <dd className="mt-1 font-medium text-slate-900">
                  {incident.service} ({incident.environment})
                </dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Event Source</dt>
                <dd className="mt-1 font-mono text-slate-900">{incident.source}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Affected Services & Tags</dt>
                <dd className="mt-1 text-slate-900">
                  {incident.affected_services.join(", ") || incident.service}
                  {incident.tags.length > 0 && ` · [${incident.tags.join(", ")}]`}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">
                  <label htmlFor="assignee-select">Assignee</label>
                </dt>
                <dd className="mt-1">
                  <select
                    id="assignee-select"
                    disabled={!canWrite || busy}
                    value={incident.assignee_user_id ?? ""}
                    onChange={(e) => handleAssign(e.target.value)}
                    className="w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 disabled:bg-slate-100"
                  >
                    <option value="">Unassigned</option>
                    {members.map((m) => (
                      <option key={m.user_id} value={m.user_id}>
                        {m.full_name} ({m.role})
                      </option>
                    ))}
                  </select>
                </dd>
              </div>
            </dl>
          </section>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Evidence Panel */}
            <section className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-slate-900">Evidence References</h2>
                <button
                  type="button"
                  disabled={!canWrite || busy}
                  title={
                    canWrite
                      ? "Fetch read-only GitHub commits, PRs, and deployments"
                      : "Requires Engineer, Admin, or Owner role"
                  }
                  onClick={() =>
                    incident &&
                    runAction(async () => {
                      const res = await api.correlateGitHub(incident.id);
                      setGhDisclaimer(res.disclaimer);
                    })
                  }
                  className="rounded border border-indigo-300 bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-800 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Correlate GitHub Evidence (Read-Only)
                </button>
              </div>
              {ghDisclaimer && (
                <p className="mt-2 rounded border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-900">
                  {ghDisclaimer}
                </p>
              )}
              <div className="mt-3 space-y-3">
                {evidence.length === 0 ? (
                  <EmptyState
                    title="No evidence attached"
                    description="Attach logs, metrics, trace links, or correlate read-only GitHub activity."
                  />
                ) : (
                  <ul className="space-y-2">
                    {evidence.map((ev) => (
                      <li key={ev.id} className="rounded-md border border-slate-200 p-3 text-xs">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold uppercase text-indigo-700">
                              {ev.kind}
                            </span>
                            {ev.metadata_json?.mode === "mock" && (
                              <span className="rounded bg-violet-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-violet-800">
                                DEMO/MOCK
                              </span>
                            )}
                            {ev.metadata_json?.mode === "live" && (
                              <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-emerald-800">
                                LIVE
                              </span>
                            )}
                          </div>
                          <span className="text-slate-400">
                            {new Date(ev.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="mt-1 font-medium text-slate-900">{ev.title}</p>
                        {ev.summary && <p className="mt-0.5 text-slate-600">{ev.summary}</p>}
                        {ev.uri && (
                          <p className="mt-1 truncate font-mono text-indigo-600">{ev.uri}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}

                {canWrite && (
                  <form
                    onSubmit={handleAddEvidence}
                    className="space-y-2 border-t border-slate-100 pt-3"
                  >
                    <p className="text-xs font-medium text-slate-700">Attach evidence</p>
                    <div className="flex gap-2">
                      <select
                        aria-label="Evidence kind"
                        value={evKind}
                        onChange={(e) => setEvKind(e.target.value as EvidenceKind)}
                        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs"
                      >
                        <option value="log">log</option>
                        <option value="metric">metric</option>
                        <option value="trace">trace</option>
                        <option value="commit">commit</option>
                        <option value="runbook">runbook</option>
                        <option value="link">link</option>
                      </select>
                      <input
                        required
                        minLength={2}
                        value={evTitle}
                        onChange={(e) => setEvTitle(e.target.value)}
                        placeholder="Evidence title"
                        className="flex-1 rounded-md border border-slate-300 px-2.5 py-1 text-xs"
                      />
                    </div>
                    <input
                      value={evUri}
                      onChange={(e) => setEvUri(e.target.value)}
                      placeholder="Reference URI (optional)"
                      className="w-full rounded-md border border-slate-300 px-2.5 py-1 text-xs"
                    />
                    <input
                      value={evSummary}
                      onChange={(e) => setEvSummary(e.target.value)}
                      placeholder="Summary (optional)"
                      className="w-full rounded-md border border-slate-300 px-2.5 py-1 text-xs"
                    />
                    <button
                      type="submit"
                      disabled={busy}
                      className="rounded-md bg-slate-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-900 disabled:opacity-50"
                    >
                      Attach Evidence
                    </button>
                  </form>
                )}
              </div>
            </section>

            {/* Comments */}
            <section className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">Notes & Comments</h2>
              <div className="mt-3 space-y-3">
                {comments.length === 0 ? (
                  <EmptyState
                    title="No comments yet"
                    description="Record triage findings or handoff notes."
                  />
                ) : (
                  <ul className="space-y-2">
                    {comments.map((c) => (
                      <li key={c.id} className="rounded-md bg-slate-50 p-3 text-xs">
                        <div className="flex justify-between text-slate-500">
                          <span className="font-semibold text-slate-800">
                            {memberName(c.author_user_id)}
                          </span>
                          <span>{new Date(c.created_at).toLocaleString()}</span>
                        </div>
                        <p className="mt-1 whitespace-pre-wrap text-slate-700">{c.body}</p>
                      </li>
                    ))}
                  </ul>
                )}

                {canWrite && (
                  <form
                    onSubmit={handleAddComment}
                    className="space-y-2 border-t border-slate-100 pt-3"
                  >
                    <label htmlFor="comment-body" className="block text-xs font-medium text-slate-700">
                      Add note
                    </label>
                    <textarea
                      id="comment-body"
                      rows={2}
                      required
                      value={commentBody}
                      onChange={(e) => setCommentBody(e.target.value)}
                      placeholder="Add investigation note..."
                      className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs"
                    />
                    <button
                      type="submit"
                      disabled={busy}
                      className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                    >
                      Post Note
                    </button>
                  </form>
                )}
              </div>
            </section>
          </div>

          {/* Timeline & Audit History */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <section className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">Incident Timeline</h2>
              <ul className="mt-3 space-y-2.5">
                {timeline.map((ev) => (
                  <li key={ev.id} className="border-l-2 border-indigo-200 pl-3 text-xs">
                    <p className="font-medium text-slate-900">{ev.message}</p>
                    <p className="text-slate-500">
                      {memberName(ev.actor_user_id)} · {ev.event_type} ·{" "}
                      {new Date(ev.created_at).toLocaleString()}
                    </p>
                  </li>
                ))}
              </ul>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">Audit History</h2>
              {!canReadAudit ? (
                <p className="mt-2 text-xs text-slate-500">
                  Security audit history requires Admin or Owner role.
                </p>
              ) : auditLogs.length === 0 ? (
                <p className="mt-2 text-xs text-slate-500">No audit entries recorded yet.</p>
              ) : (
                <ul className="mt-3 space-y-2 text-xs">
                  {auditLogs.map((log) => (
                    <li key={log.id} className="rounded bg-slate-50 p-2">
                      <span className="font-mono font-semibold text-slate-800">{log.action}</span>
                      <span className="ml-2 text-slate-500">
                        req:{log.request_id.slice(0, 8)} ·{" "}
                        {new Date(log.created_at).toLocaleString()}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          {/* AI Investigation Copilot (Read-Only) */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-sm font-semibold text-slate-900">
                    AI Investigation Copilot (Read-Only)
                  </h2>
                  {aiStatus && (
                    <span
                      className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ${
                        aiStatus.provider_mode === "openai"
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-violet-100 text-violet-800"
                      }`}
                    >
                      {aiStatus.provider_mode === "openai" ? "OPENAI LIVE" : "MOCK / DETERMINISTIC"}
                    </span>
                  )}
                </div>
                {aiStatus && (
                  <p className="mt-0.5 text-xs text-slate-500">
                    Model: <span className="font-mono">{aiStatus.model_name}</span> · Daily tenant
                    quota: {aiStatus.tenant_daily_used}/{aiStatus.tenant_daily_quota} ·{" "}
                    {aiStatus.notice}
                  </p>
                )}
              </div>
              <button
                type="button"
                disabled={!canWrite || busy || (aiStatus ? !aiStatus.configured : false)}
                title={
                  canWrite
                    ? "Run bounded read-only AI investigation across logs, GitHub, and KB"
                    : "Requires Engineer, Admin, or Owner role"
                }
                onClick={() =>
                  incident &&
                  runAction(async () => {
                    await api.startInvestigation(incident.id, 24);
                  })
                }
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Investigating..." : "Start Read-Only Investigation"}
              </button>
            </div>

            {investigations.length === 0 ? (
              <div className="mt-3">
                <EmptyState
                  title="No AI investigations yet"
                  description="Start a bounded read-only investigation to correlate logs, GitHub changes, and runbooks."
                />
              </div>
            ) : (
              <div className="mt-4 space-y-4">
                {investigations.slice(0, 1).map((run) => (
                  <div key={run.id} className="space-y-3 rounded-md border border-slate-200 p-4 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold text-slate-900">
                          Run #{run.id}
                        </span>
                        <span
                          className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase ${
                            run.status === "completed"
                              ? "bg-emerald-100 text-emerald-800"
                              : run.status === "failed"
                                ? "bg-rose-100 text-rose-800"
                                : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {run.status}
                        </span>
                        <span className="text-slate-500">
                          {run.tool_calls_count} tools · {run.latency_ms}ms · {run.input_tokens}+
                          {run.output_tokens} tok
                        </span>
                      </div>
                      {(run.status === "pending" || run.status === "running") && canWrite && (
                        <button
                          type="button"
                          onClick={() => runAction(() => api.cancelInvestigation(run.id))}
                          className="rounded border border-rose-300 px-2 py-1 text-[11px] text-rose-700 hover:bg-rose-50"
                        >
                          Cancel
                        </button>
                      )}
                    </div>

                    {run.error_message && (
                      <p className="rounded border border-rose-200 bg-rose-50 p-2 text-rose-800">
                        {run.error_message}
                      </p>
                    )}

                    {/* Tool activity trace */}
                    <div>
                      <p className="font-semibold uppercase tracking-wide text-slate-500">
                        Approved Tool Activity
                      </p>
                      <div className="mt-1 flex flex-wrap gap-2">
                        {run.tool_calls.map((tc) => (
                          <span
                            key={tc.id}
                            className="rounded border border-slate-200 bg-slate-50 px-2 py-1 font-mono text-[11px] text-slate-700"
                          >
                            {tc.tool_name}: {tc.status} ({tc.output_count} items, {tc.latency_ms}ms)
                          </span>
                        ))}
                      </div>
                    </div>

                    {run.report_json && (
                      <div className="space-y-3 border-t border-slate-100 pt-3">
                        {run.report_json.insufficient_evidence && (
                          <div className="rounded border border-amber-300 bg-amber-50 p-2.5 text-amber-900">
                            <strong>Insufficient Evidence:</strong> Telemetry is too sparse to
                            determine a root cause.
                          </div>
                        )}
                        {run.report_json.conflicting_evidence && (
                          <div className="rounded border border-amber-300 bg-amber-50 p-2.5 text-amber-900">
                            <strong>Conflicting Signals:</strong> Evidence sources disagree; verify
                            manually.
                          </div>
                        )}
                        <div>
                          <p className="font-semibold text-slate-800">Summary</p>
                          <p className="mt-0.5 text-slate-700">{run.report_json.summary}</p>
                        </div>
                        {run.report_json.observed_facts.length > 0 && (
                          <div>
                            <p className="font-semibold text-slate-800">Observed Facts</p>
                            <ul className="mt-1 list-disc space-y-1 pl-4 text-slate-700">
                              {run.report_json.observed_facts.map((f, i) => (
                                <li key={i}>
                                  {f.statement}{" "}
                                  <span className="font-mono text-[10px] text-indigo-700">
                                    [{f.evidence_ids.join(", ")}]
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {run.report_json.possible_causes.length > 0 && (
                          <div>
                            <p className="font-semibold text-slate-800">
                              Possible Causes (Hypotheses)
                            </p>
                            <ul className="mt-1 space-y-1.5">
                              {run.report_json.possible_causes.map((c, i) => (
                                <li key={i} className="rounded bg-slate-50 p-2">
                                  <div className="flex items-center gap-2">
                                    <span
                                      className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase ${
                                        c.confidence === "high"
                                          ? "bg-emerald-100 text-emerald-800"
                                          : c.confidence === "medium"
                                            ? "bg-amber-100 text-amber-800"
                                            : "bg-slate-200 text-slate-700"
                                      }`}
                                    >
                                      {c.confidence} confidence
                                    </span>
                                    <span className="font-medium text-slate-900">
                                      {c.hypothesis}
                                    </span>
                                  </div>
                                  <p className="mt-1 text-slate-600">{c.rationale}</p>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {run.report_json.missing_information.length > 0 && (
                          <div>
                            <p className="font-semibold text-slate-800">Missing Information</p>
                            <ul className="mt-1 list-disc pl-4 text-slate-600">
                              {run.report_json.missing_information.map((m, i) => (
                                <li key={i}>{m}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {run.report_json.recommended_diagnostics.length > 0 && (
                          <div>
                            <p className="font-semibold text-slate-800">
                              Recommended Read-Only Diagnostics
                            </p>
                            <ul className="mt-1 list-disc pl-4 text-slate-600">
                              {run.report_json.recommended_diagnostics.map((d, i) => (
                                <li key={i}>{d}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Human feedback */}
                        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2">
                          <span className="font-medium text-slate-600">Human feedback:</span>
                          {(["helpful", "not_helpful", "inaccurate"] as const).map((rating) => (
                            <button
                              key={rating}
                              type="button"
                              disabled={busy}
                              onClick={() =>
                                runAction(async () => {
                                  await api.submitInvestigationFeedback(
                                    run.id,
                                    rating,
                                    feedbackNote || undefined,
                                  );
                                  setFeedbackNote("");
                                })
                              }
                              className={`rounded border px-2 py-0.5 text-[11px] ${
                                run.human_feedback_rating === rating
                                  ? "border-indigo-600 bg-indigo-50 font-semibold text-indigo-800"
                                  : "border-slate-300 text-slate-700 hover:bg-slate-50"
                              }`}
                            >
                              {rating.replace("_", " ")}
                            </button>
                          ))}
                          <input
                            type="text"
                            placeholder="Optional feedback note..."
                            value={feedbackNote}
                            onChange={(e) => setFeedbackNote(e.target.value)}
                            className="rounded border border-slate-300 px-2 py-0.5 text-[11px]"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Proposed External Actions (Human Approval Gate, Phase 9) */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  Proposed External Actions (Human Approval Gate)
                </h2>
                <p className="text-xs text-slate-500">
                  Jira issues and Slack notifications require explicit approval and server-side
                  re-authorization before execution.
                </p>
              </div>
              <Link href="/actions" className="text-xs font-medium text-indigo-600 hover:underline">
                View All Action Approvals →
              </Link>
            </div>

            {proposedActions.length === 0 ? (
              <div className="mt-3">
                <EmptyState
                  title="No proposed external actions"
                  description="Propose a Jira issue or Slack message below after configuring a connector in Settings."
                />
              </div>
            ) : (
              <ul className="mt-3 space-y-2.5 text-xs">
                {proposedActions.map((act) => (
                  <li key={act.id} className="rounded-md border border-slate-200 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-mono font-semibold text-slate-900">
                          {act.action_type} → {act.target_destination}
                        </span>
                        <span
                          className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ${
                            act.connector_mode === "live"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-violet-100 text-violet-800"
                          }`}
                        >
                          {act.connector_mode === "live" ? "LIVE" : "DEMO / MOCK"}
                        </span>
                        <span className="rounded bg-indigo-50 px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase text-indigo-800">
                          {act.status}
                        </span>
                      </div>
                      {act.external_id && (
                        <span className="font-mono font-semibold text-emerald-700">
                          {act.external_id}
                        </span>
                      )}
                    </div>
                    <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 font-mono text-[11px] text-slate-700">
                      {JSON.stringify(act.payload_preview_json, null, 2)}
                    </pre>
                    {act.last_error && (
                      <p className="mt-1.5 rounded bg-rose-50 p-1.5 text-rose-800">
                        {act.last_error}
                      </p>
                    )}
                    {canWrite && (
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {act.status === "proposed" && (
                          <>
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => runAction(() => api.approveAction(act.id))}
                              className="rounded bg-emerald-600 px-2.5 py-1 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                            >
                              Approve
                            </button>
                            <input
                              type="text"
                              placeholder="Rejection reason..."
                              value={actRejectReason[act.id] ?? ""}
                              onChange={(e) =>
                                setActRejectReason((prev) => ({
                                  ...prev,
                                  [act.id]: e.target.value,
                                }))
                              }
                              className="rounded border border-slate-300 px-2 py-1 text-xs"
                            />
                            <button
                              type="button"
                              disabled={busy || !(actRejectReason[act.id] ?? "").trim()}
                              onClick={() =>
                                runAction(async () => {
                                  await api.rejectAction(
                                    act.id,
                                    (actRejectReason[act.id] ?? "").trim(),
                                  );
                                })
                              }
                              className="rounded border border-rose-300 px-2.5 py-1 font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {(act.status === "approved" || act.status === "failed") && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => runAction(() => api.executeAction(act.id))}
                            className="rounded bg-indigo-600 px-2.5 py-1 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                          >
                            {act.status === "failed" ? "Safe Retry" : "Execute"}
                          </button>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {canWrite && actionConnectors.length > 0 && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const conn = actionConnectors.find((c) => c.id === selectedConnId);
                  if (!conn || !incident) return;
                  const actionType =
                    conn.provider === "jira" ? "jira_create_issue" : "slack_post_message";
                  const payload =
                    conn.provider === "jira"
                      ? { summary: actSummary.trim(), description: actBody.trim() }
                      : { text: actBody.trim() };
                  void runAction(async () => {
                    await api.proposeAction(incident.id, {
                      connector_id: conn.id,
                      action_type: actionType,
                      target_destination: actDestination,
                      payload,
                    });
                    setActSummary("");
                    setActBody("");
                  });
                }}
                className="mt-4 space-y-2 border-t border-slate-100 pt-3 text-xs"
              >
                <p className="font-semibold text-slate-800">Propose External Action</p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <select
                    aria-label="Select action connector"
                    required
                    value={selectedConnId}
                    onChange={(e) => {
                      const cid = Number(e.target.value);
                      setSelectedConnId(cid);
                      const c = actionConnectors.find((x) => x.id === cid);
                      setActDestination(c?.allowed_targets_json[0] ?? "");
                    }}
                    className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5"
                  >
                    <option value="">Select Jira or Slack connector...</option>
                    {actionConnectors.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.provider} · {c.mode.toUpperCase()})
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Select allowlisted destination"
                    required
                    value={actDestination}
                    onChange={(e) => setActDestination(e.target.value)}
                    className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5"
                  >
                    <option value="">Select allowlisted target...</option>
                    {(
                      actionConnectors.find((c) => c.id === selectedConnId)?.allowed_targets_json ??
                      []
                    ).map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                {actionConnectors.find((c) => c.id === selectedConnId)?.provider === "jira" && (
                  <input
                    required
                    minLength={4}
                    placeholder="Jira issue summary..."
                    value={actSummary}
                    onChange={(e) => setActSummary(e.target.value)}
                    className="w-full rounded-md border border-slate-300 px-2.5 py-1.5"
                  />
                )}
                <textarea
                  required
                  minLength={4}
                  rows={2}
                  placeholder="Jira description or Slack message text..."
                  value={actBody}
                  onChange={(e) => setActBody(e.target.value)}
                  className="w-full rounded-md border border-slate-300 p-2"
                />
                <button
                  type="submit"
                  disabled={busy || !selectedConnId || !actDestination}
                  className="rounded-md bg-slate-800 px-3 py-1.5 font-medium text-white hover:bg-slate-900 disabled:opacity-50"
                >
                  Propose Action (Requires Approval)
                </button>
              </form>
            )}
          </section>

          {evContext && (
            <section className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">
                    Normalized Evidence Context (Logs &amp; Runbooks)
                  </h2>
                  <p className="text-xs text-slate-500">
                    Service: {evContext.affected_service ?? "all"} · Window:{" "}
                    {new Date(evContext.window_start).toLocaleString()} –{" "}
                    {new Date(evContext.window_end).toLocaleString()}
                  </p>
                </div>
                <Link
                  href="/evidence"
                  className="text-xs font-medium text-indigo-600 hover:underline"
                >
                  Open Evidence &amp; KB Explorer →
                </Link>
              </div>
              <p className="mt-2 rounded border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-900">
                {evContext.trust_boundary}
              </p>
              <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Recent Service Logs ({evContext.logs.length})
                  </h3>
                  {evContext.logs.length === 0 ? (
                    <p className="mt-2 text-xs text-slate-500">
                      No logs matched this service in the 24h window.
                    </p>
                  ) : (
                    <ul className="mt-2 space-y-2 text-xs">
                      {evContext.logs.slice(0, 5).map((l) => (
                        <li key={l.id} className="rounded border border-slate-200 p-2">
                          <div className="flex items-center gap-1.5 font-mono text-[10px]">
                            <span className="font-semibold text-slate-800">{l.severity}</span>
                            {l.is_synthetic && (
                              <span className="rounded bg-violet-100 px-1 text-violet-800">
                                SYNTHETIC
                              </span>
                            )}
                            <span className="text-slate-400">
                              {new Date(l.timestamp).toISOString().slice(11, 19)}Z
                            </span>
                          </div>
                          <p className="mt-1 text-slate-700">{l.message}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Matched Knowledge Passages ({evContext.knowledge_hits.length})
                  </h3>
                  {evContext.knowledge_hits.length === 0 ? (
                    <p className="mt-2 text-xs text-slate-500">
                      No matching runbook passages found.
                    </p>
                  ) : (
                    <ul className="mt-2 space-y-2 text-xs">
                      {evContext.knowledge_hits.map((hit) => (
                        <li key={hit.chunk_id} className="rounded border border-slate-200 p-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium text-slate-900">
                              {hit.document_title}
                            </span>
                            {hit.is_synthetic && (
                              <span className="rounded bg-violet-100 px-1 font-mono text-[10px] text-violet-800">
                                SYNTHETIC
                              </span>
                            )}
                          </div>
                          <p className="font-mono text-[10px] text-slate-500">
                            {hit.source_uri} (v{hit.version} · score {hit.hybrid_score.toFixed(2)})
                          </p>
                          <p className="mt-1 text-slate-600">{hit.snippet}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </section>
          )}
        </div>
      ) : null}
    </AppShell>
  );
}
