"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { SimulatedBadge } from "@/components/Badges";
import { EmptyState, ErrorAlert, LoadingSkeleton } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { InboundEvent, InboundEventStatus } from "@/lib/types";

export default function EventsPage() {
  const { can } = useAuth();
  const canRead = can("event:read");
  const canReplay = can("event:replay");

  const [events, setEvents] = useState<InboundEvent[]>([]);
  const [statusFilter, setStatusFilter] = useState<InboundEventStatus | "">("");
  const [simFilter, setSimFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [replayingId, setReplayingId] = useState<number | null>(null);

  const loadEvents = useCallback(async () => {
    if (!canRead) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const list = await api.listEvents({ status: statusFilter, is_simulated: simFilter });
      setEvents(list);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [canRead, statusFilter, simFilter]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  const handleReplay = async (eventId: number) => {
    setReplayingId(eventId);
    setError(null);
    try {
      await api.replayEvent(eventId);
      await loadEvents();
    } catch (err) {
      setError(err);
    } finally {
      setReplayingId(null);
    }
  };

  return (
    <AppShell>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Ingestion & Failed Events</h1>
          <p className="text-sm text-slate-500">
            Inbound webhook receipts, retry state, correlation IDs, and dead-letter replay.
          </p>
        </div>
        {canRead && (
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="Filter event status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as InboundEventStatus | "")}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm"
            >
              <option value="">All statuses</option>
              <option value="dead_letter">dead_letter</option>
              <option value="retrying">retrying</option>
              <option value="received">received</option>
              <option value="queued">queued</option>
              <option value="processed">processed</option>
            </select>
            <select
              aria-label="Filter simulated events"
              value={simFilter}
              onChange={(e) => setSimFilter(e.target.value)}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm"
            >
              <option value="">Live & Simulated</option>
              <option value="false">Live only</option>
              <option value="true">Simulated only</option>
            </select>
          </div>
        )}
      </div>

      {!canRead ? (
        <div className="mt-6">
          <EmptyState
            title="Restricted to Admin and Owner roles"
            description="Your current role cannot inspect inbound webhook receipts or replay dead-letter events."
          />
        </div>
      ) : (
        <div className="mt-6 space-y-4">
          {error !== null && <ErrorAlert error={error} onRetry={loadEvents} />}
          {loading ? (
            <LoadingSkeleton rows={4} />
          ) : events.length === 0 ? (
            <EmptyState
              title="No inbound events"
              description="Send an Alertmanager webhook or run the simulator in Settings to see receipts here."
            />
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                <thead className="bg-slate-50 font-semibold uppercase tracking-wide text-slate-600">
                  <tr>
                    <th className="px-4 py-3">Event</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Attempts</th>
                    <th className="px-4 py-3">Correlation ID</th>
                    <th className="px-4 py-3">Incident</th>
                    <th className="px-4 py-3">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {events.map((ev) => (
                    <tr key={ev.id}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-semibold text-slate-900">#{ev.id}</span>
                          {ev.is_simulated && <SimulatedBadge />}
                        </div>
                        <p className="mt-0.5 font-mono text-slate-500">{ev.fingerprint}</p>
                        {ev.last_error && (
                          <p className="mt-0.5 text-rose-700">{ev.last_error}</p>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono">{ev.status}</td>
                      <td className="px-4 py-3 tabular-nums">
                        {ev.attempt_count}/{ev.max_attempts}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-500">{ev.correlation_id}</td>
                      <td className="px-4 py-3">
                        {ev.incident_id ? (
                          <Link
                            href={`/incidents/${ev.incident_id}`}
                            className="font-medium text-indigo-600 hover:underline"
                          >
                            Incident #{ev.incident_id}
                          </Link>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          disabled={!canReplay || replayingId === ev.id}
                          onClick={() => handleReplay(ev.id)}
                          className="inline-flex items-center gap-1 rounded border border-slate-300 px-2.5 py-1 font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                        >
                          <RefreshCw className="h-3 w-3" aria-hidden="true" />
                          <span>{replayingId === ev.id ? "Replaying..." : "Replay"}</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </AppShell>
  );
}
