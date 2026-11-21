import type { IncidentStatus, Role, Severity } from "@/lib/types";

const SEVERITY_STYLES: Record<Severity, string> = {
  critical: "bg-rose-100 text-rose-800 border-rose-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-amber-100 text-amber-800 border-amber-200",
  low: "bg-sky-100 text-sky-800 border-sky-200",
};

const STATUS_STYLES: Record<IncidentStatus, string> = {
  open: "bg-rose-50 text-rose-700 border-rose-200",
  acknowledged: "bg-indigo-50 text-indigo-700 border-indigo-200",
  investigating: "bg-amber-50 text-amber-800 border-amber-200",
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  closed: "bg-slate-100 text-slate-700 border-slate-200",
};

const ROLE_STYLES: Record<Role, string> = {
  owner: "bg-purple-100 text-purple-800 border-purple-200",
  admin: "bg-indigo-100 text-indigo-800 border-indigo-200",
  engineer: "bg-teal-100 text-teal-800 border-teal-200",
  viewer: "bg-slate-100 text-slate-700 border-slate-200",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${SEVERITY_STYLES[severity]}`}
    >
      {severity}
    </span>
  );
}

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium capitalize ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}

export function RoleBadge({ role }: { role: Role }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${ROLE_STYLES[role]}`}
    >
      {role}
    </span>
  );
}

export function SimulatedBadge() {
  return (
    <span className="inline-flex items-center rounded-md border border-violet-200 bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-800">
      Simulated
    </span>
  );
}
