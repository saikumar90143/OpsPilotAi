"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Plus, Search } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { SeverityBadge, SimulatedBadge, StatusBadge } from "@/components/Badges";
import { EmptyState, ErrorAlert, LoadingSkeleton } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Environment, Incident, IncidentStatus, Severity } from "@/lib/types";

const PAGE_SIZE = 15;

export default function IncidentsPage() {
  const { can } = useAuth();
  const canWrite = can("incident:write");

  const [items, setItems] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | "">("");
  const [severityFilter, setSeverityFilter] = useState<Severity | "">("");
  const [sortBy, setSortBy] = useState<"created_at" | "updated_at" | "severity" | "status">(
    "created_at",
  );
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [offset, setOffset] = useState(0);

  const [createOpen, setCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newService, setNewService] = useState("");
  const [newEnv, setNewEnv] = useState<Environment>("production");
  const [newSeverity, setNewSeverity] = useState<Severity>("high");
  const [newDesc, setNewDesc] = useState("");
  const [newTags, setNewTags] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<unknown>(null);

  const loadIncidents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listIncidents({
        limit: PAGE_SIZE,
        offset,
        q: q.trim() || undefined,
        status: statusFilter,
        severity: severityFilter,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [offset, q, statusFilter, severityFilter, sortBy, sortOrder]);

  useEffect(() => {
    void loadIncidents();
  }, [loadIncidents]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await api.createIncident({
        title: newTitle.trim(),
        description: newDesc.trim(),
        service: newService.trim(),
        environment: newEnv,
        severity: newSeverity,
        tags: newTags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      });
      setCreateOpen(false);
      setNewTitle("");
      setNewService("");
      setNewDesc("");
      setNewTags("");
      setOffset(0);
      await loadIncidents();
    } catch (err) {
      setCreateError(err);
    } finally {
      setCreating(false);
    }
  };

  return (
    <AppShell>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Incidents</h1>
          <p className="text-sm text-slate-500">
            Search, filter, and triage active incidents in your organization.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={!canWrite}
            title={canWrite ? "Create a manual incident" : "Viewer role cannot create incidents"}
            onClick={() => setCreateOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3.5 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            <span>New Incident</span>
          </button>
        </div>
      </div>

      {!canWrite && (
        <p className="mt-2 text-xs text-slate-500">
          Your role is read-only (<code className="font-mono">viewer</code>); incident creation is
          disabled.
        </p>
      )}

      {/* Filters */}
      <section
        aria-label="Incident filters"
        className="mt-5 grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-5"
      >
        <div className="relative lg:col-span-2">
          <label htmlFor="incident-search" className="sr-only">
            Search incidents
          </label>
          <Search
            className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400"
            aria-hidden="true"
          />
          <input
            id="incident-search"
            type="search"
            value={q}
            onChange={(e) => {
              setOffset(0);
              setQ(e.target.value);
            }}
            placeholder="Search title, description, or service..."
            className="w-full rounded-md border border-slate-300 py-1.5 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400"
          />
        </div>

        <div>
          <label htmlFor="filter-status" className="sr-only">
            Filter by status
          </label>
          <select
            id="filter-status"
            value={statusFilter}
            onChange={(e) => {
              setOffset(0);
              setStatusFilter(e.target.value as IncidentStatus | "");
            }}
            className="w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900"
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
        </div>

        <div>
          <label htmlFor="filter-severity" className="sr-only">
            Filter by severity
          </label>
          <select
            id="filter-severity"
            value={severityFilter}
            onChange={(e) => {
              setOffset(0);
              setSeverityFilter(e.target.value as Severity | "");
            }}
            className="w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900"
          >
            <option value="">All severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div className="flex gap-2">
          <label htmlFor="sort-by" className="sr-only">
            Sort by
          </label>
          <select
            id="sort-by"
            value={`${sortBy}:${sortOrder}`}
            onChange={(e) => {
              const [field, ord] = e.target.value.split(":") as [
                "created_at" | "updated_at" | "severity" | "status",
                "asc" | "desc",
              ];
              setOffset(0);
              setSortBy(field);
              setSortOrder(ord);
            }}
            className="w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900"
          >
            <option value="created_at:desc">Newest first</option>
            <option value="created_at:asc">Oldest first</option>
            <option value="severity:desc">Highest severity</option>
            <option value="updated_at:desc">Recently updated</option>
          </select>
        </div>
      </section>

      {error !== null && (
        <div className="mt-5">
          <ErrorAlert error={error} onRetry={loadIncidents} />
        </div>
      )}

      <div className="mt-5">
        {loading ? (
          <LoadingSkeleton rows={5} />
        ) : items.length === 0 ? (
          <EmptyState
            title="No matching incidents"
            description="Try clearing search or filter criteria, or create a new incident."
          />
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <ul className="divide-y divide-slate-200">
              {items.map((inc) => (
                <li key={inc.id}>
                  <Link
                    href={`/incidents/${inc.id}`}
                    className="flex flex-col gap-2 px-5 py-4 hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-slate-400">#{inc.id}</span>
                        <p className="truncate text-sm font-semibold text-slate-900">{inc.title}</p>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {inc.service} · {inc.environment} · source: {inc.source} ·{" "}
                        {new Date(inc.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-2">
                      {Boolean(inc.metadata?.simulated) && <SimulatedBadge />}
                      <SeverityBadge severity={inc.severity} />
                      <StatusBadge status={inc.status} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Pagination */}
      {total > 0 && (
        <div className="mt-4 flex items-center justify-between text-xs text-slate-600">
          <span className="tabular-nums">
            Showing {offset + 1}–{Math.min(offset + items.length, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Create modal */}
      {createOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-incident-title"
        >
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <h2 id="create-incident-title" className="text-base font-semibold text-slate-900">
              Create Incident
            </h2>
            <form onSubmit={handleCreate} className="mt-4 space-y-3">
              {createError !== null && <ErrorAlert error={createError} />}
              <div>
                <label htmlFor="new-title" className="block text-xs font-medium text-slate-700">
                  Title
                </label>
                <input
                  id="new-title"
                  required
                  minLength={4}
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                />
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <label htmlFor="new-service" className="block text-xs font-medium text-slate-700">
                    Service
                  </label>
                  <input
                    id="new-service"
                    required
                    minLength={2}
                    value={newService}
                    onChange={(e) => setNewService(e.target.value)}
                    placeholder="checkout-api"
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                  />
                </div>
                <div>
                  <label htmlFor="new-env" className="block text-xs font-medium text-slate-700">
                    Environment
                  </label>
                  <select
                    id="new-env"
                    value={newEnv}
                    onChange={(e) => setNewEnv(e.target.value as Environment)}
                    className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm"
                  >
                    <option value="production">production</option>
                    <option value="staging">staging</option>
                    <option value="development">development</option>
                    <option value="unknown">unknown</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="new-sev" className="block text-xs font-medium text-slate-700">
                    Severity
                  </label>
                  <select
                    id="new-sev"
                    value={newSeverity}
                    onChange={(e) => setNewSeverity(e.target.value as Severity)}
                    className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm"
                  >
                    <option value="critical">critical</option>
                    <option value="high">high</option>
                    <option value="medium">medium</option>
                    <option value="low">low</option>
                  </select>
                </div>
              </div>
              <div>
                <label htmlFor="new-desc" className="block text-xs font-medium text-slate-700">
                  Description
                </label>
                <textarea
                  id="new-desc"
                  rows={3}
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                />
              </div>
              <div>
                <label htmlFor="new-tags" className="block text-xs font-medium text-slate-700">
                  Tags (comma-separated)
                </label>
                <input
                  id="new-tags"
                  value={newTags}
                  onChange={(e) => setNewTags(e.target.value)}
                  placeholder="latency, db"
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCreateOpen(false)}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-md bg-indigo-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
                >
                  {creating ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
