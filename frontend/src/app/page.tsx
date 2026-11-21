"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { SeverityBadge, SimulatedBadge, StatusBadge } from "@/components/Badges";
import { EmptyState, ErrorAlert, LoadingSkeleton } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { InboundEvent, Incident, Severity } from "@/lib/types";

type TimeRange = "24h" | "7d" | "30d" | "all";

const TIME_RANGES: Array<{ value: TimeRange; label: string }> = [
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "all", label: "All time" },
];

function createdAfterIso(range: TimeRange): string | undefined {
  if (range === "all") return undefined;
  const hours = range === "24h" ? 24 : range === "7d" ? 24 * 7 : 24 * 30;
  return new Date(Date.now() - hours * 3600 * 1000).toISOString();
}

export default function OverviewPage() {
  const { can } = useAuth();
  const [range, setRange] = useState<TimeRange>("30d");
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [totalIncidents, setTotalIncidents] = useState(0);
  const [events, setEvents] = useState<InboundEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const canReadEvents = can("event:read");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const createdAfter = createdAfterIso(range);
      const incRes = await api.listIncidents({
        limit: 100,
        created_after: createdAfter,
        sort_by: "created_at",
        sort_order: "desc",
      });
      setIncidents(incRes.items);
      setTotalIncidents(incRes.total);

      if (canReadEvents) {
        const evRes = await api.listEvents();
        setEvents(evRes);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [range, canReadEvents]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const openCount = incidents.filter((i) => i.status === "open").length;
  const activeCount = incidents.filter(
    (i) => i.status === "acknowledged" || i.status === "investigating",
  ).length;
  const resolvedCount = incidents.filter(
    (i) => i.status === "resolved" || i.status === "closed",
  ).length;
  const deadLetterCount = events.filter((e) => e.status === "dead_letter").length;

  const severities: Severity[] = ["critical", "high", "medium", "low"];
  const severityCounts = severities.map((sev) => ({
    severity: sev,
    count: incidents.filter((i) => i.severity === sev).length,
  }));

  return (
    <AppShell>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Operations Overview</h1>
          <p className="text-sm text-slate-500">
            Live incident posture and ingestion health for your organization.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="time-range" className="text-xs font-medium text-slate-600">
            Time window
          </label>
          <select
            id="time-range"
            value={range}
            onChange={(e) => setRange(e.target.value as TimeRange)}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900"
          >
            {TIME_RANGES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error !== null && (
        <div className="mt-5">
          <ErrorAlert error={error} onRetry={loadData} />
        </div>
      )}

      {loading ? (
        <div className="mt-6">
          <LoadingSkeleton rows={4} />
        </div>
      ) : (
        <>
          <section
            aria-label="Incident summary metrics"
            className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
          >
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Total in Window
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">
                {totalIncidents}
              </p>
              {totalIncidents > incidents.length && (
                <p className="mt-1 text-xs text-slate-500">
                  Breakdown below reflects newest {incidents.length}
                </p>
              )}
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Open</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-rose-700">{openCount}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Ack / Investigating
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-amber-700">
                {activeCount}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Resolved / Closed
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-emerald-700">
                {resolvedCount}
              </p>
            </div>
          </section>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
            <section className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">Severity Distribution</h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Computed from returned incidents in the selected window.
              </p>
              <div className="mt-4 space-y-3">
                {severityCounts.map(({ severity, count }) => {
                  const pct =
                    incidents.length > 0 ? Math.round((count / incidents.length) * 100) : 0;
                  return (
                    <div key={severity}>
                      <div className="flex items-center justify-between text-xs">
                        <SeverityBadge severity={severity} />
                        <span className="font-mono tabular-nums text-slate-700">
                          {count} ({pct}%)
                        </span>
                      </div>
                      <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-slate-700"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="mt-6 border-t border-slate-100 pt-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Ingestion Pipeline
                </h3>
                {canReadEvents ? (
                  <div className="mt-2 flex items-center justify-between text-sm">
                    <span className="text-slate-600">
                      {events.length} recent event(s), {deadLetterCount} dead-letter
                    </span>
                    <Link
                      href="/events"
                      className="text-xs font-medium text-indigo-600 hover:text-indigo-700"
                    >
                      Inspect
                    </Link>
                  </div>
                ) : (
                  <p className="mt-1 text-xs text-slate-500">
                    Event queue inspection requires Admin or Owner role.
                  </p>
                )}
              </div>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 lg:col-span-2">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-900">Recent Incidents</h2>
                <Link
                  href="/incidents"
                  className="text-xs font-medium text-indigo-600 hover:text-indigo-700"
                >
                  View all
                </Link>
              </div>
              <div className="mt-4">
                {incidents.length === 0 ? (
                  <EmptyState
                    title="No incidents in this window"
                    description="Adjust the time window or create an incident from the Incidents page."
                  />
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {incidents.slice(0, 6).map((inc) => (
                      <li key={inc.id} className="py-3">
                        <Link
                          href={`/incidents/${inc.id}`}
                          className="flex flex-col gap-1.5 rounded-md p-1 hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-slate-900">
                              {inc.title}
                            </p>
                            <p className="text-xs text-slate-500">
                              {inc.service} · {inc.environment} ·{" "}
                              {new Date(inc.created_at).toLocaleString()}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            {Boolean(inc.metadata?.simulated) && <SimulatedBadge />}
                            <SeverityBadge severity={inc.severity} />
                            <StatusBadge status={inc.status} />
                          </div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>
          </div>
        </>
      )}
    </AppShell>
  );
}
