"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { EmptyState, ErrorAlert, LoadingSkeleton } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ProposedAction, ProposedActionStatus } from "@/lib/types";

export default function ActionsQueuePage() {
  const { session } = useAuth();
  const [actions, setActions] = useState<ProposedAction[]>([]);
  const [statusFilter, setStatusFilter] = useState<ProposedActionStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState<Record<number, string>>({});

  const canAct =
    session?.role === "owner" || session?.role === "admin" || session?.role === "engineer";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await api.listActions(statusFilter);
      setActions(items);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    if (session) void load();
  }, [session, load]);

  const handleAction = async (id: number, fn: () => Promise<unknown>) => {
    setBusyId(id);
    setError(null);
    try {
      await fn();
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <AppShell>
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">
              External Action Approvals (Human Gate)
            </h1>
            <p className="text-sm text-slate-600">
              Every Jira issue or Slack message requires explicit human approval before execution.
            </p>
          </div>
          <select
            aria-label="Filter by status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ProposedActionStatus | "")}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs"
          >
            <option value="">All statuses</option>
            <option value="proposed">PROPOSED</option>
            <option value="approved">APPROVED</option>
            <option value="succeeded">SUCCEEDED</option>
            <option value="failed">FAILED</option>
            <option value="rejected">REJECTED</option>
            <option value="expired">EXPIRED</option>
          </select>
        </div>

        {error ? <ErrorAlert error={error} /> : null}

        {loading ? (
          <LoadingSkeleton rows={4} />
        ) : actions.length === 0 ? (
          <EmptyState
            title="No proposed external actions"
            description="Propose a Jira issue or Slack message from an incident detail page."
          />
        ) : (
          <div className="space-y-3">
            {actions.map((act) => (
              <div
                key={act.id}
                className="rounded-lg border border-slate-200 bg-white p-4 text-xs shadow-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono font-semibold text-slate-900">#{act.id}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-slate-800">
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
                  <Link
                    href={`/incidents/${act.incident_id}`}
                    className="font-medium text-indigo-600 hover:underline"
                  >
                    Incident #{act.incident_id} →
                  </Link>
                </div>

                <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 font-mono text-[11px] text-slate-700">
                  {JSON.stringify(act.payload_preview_json, null, 2)}
                </pre>

                <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
                  <span>
                    Idempotency: <span className="font-mono">{act.idempotency_key}</span> ·
                    Expires: {new Date(act.expires_at).toLocaleString()}
                  </span>
                  {act.external_id && (
                    <span className="font-mono font-semibold text-emerald-700">
                      External ID: {act.external_id}
                    </span>
                  )}
                </div>

                {act.last_error && (
                  <p className="mt-2 rounded bg-rose-50 p-2 text-rose-800">{act.last_error}</p>
                )}

                {canAct && (
                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2">
                    {act.status === "proposed" && (
                      <>
                        <button
                          type="button"
                          disabled={busyId === act.id}
                          onClick={() => handleAction(act.id, () => api.approveAction(act.id))}
                          className="rounded bg-emerald-600 px-3 py-1 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                        >
                          Approve
                        </button>
                        <input
                          type="text"
                          placeholder="Rejection reason..."
                          value={rejectReason[act.id] ?? ""}
                          onChange={(e) =>
                            setRejectReason((prev) => ({ ...prev, [act.id]: e.target.value }))
                          }
                          className="rounded border border-slate-300 px-2 py-1 text-xs"
                        />
                        <button
                          type="button"
                          disabled={busyId === act.id || !(rejectReason[act.id] ?? "").trim()}
                          onClick={() =>
                            handleAction(act.id, () =>
                              api.rejectAction(act.id, (rejectReason[act.id] ?? "").trim()),
                            )
                          }
                          className="rounded border border-rose-300 px-3 py-1 font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                        >
                          Reject
                        </button>
                      </>
                    )}
                    {(act.status === "approved" || act.status === "failed") && (
                      <button
                        type="button"
                        disabled={busyId === act.id}
                        onClick={() => handleAction(act.id, () => api.executeAction(act.id))}
                        className="rounded bg-indigo-600 px-3 py-1 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                      >
                        {act.status === "failed" ? "Safe Retry Execution" : "Execute Action"}
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
