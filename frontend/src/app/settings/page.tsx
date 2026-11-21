"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleBadge } from "@/components/Badges";
import { ErrorAlert, LoadingSkeleton } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  ActionConnector,
  ActionProviderType,
  GitHubConnector,
  Integration,
  Membership,
  Role,
  ScmMode,
} from "@/lib/types";

export default function SettingsPage() {
  const { session, can, refreshSession } = useAuth();
  const canUpdateOrg = can("org:update");
  const canManageMembers = can("member:manage");
  const canReadIntegrations = can("integration:read");
  const canManageIntegrations = can("integration:manage");

  const [orgName, setOrgName] = useState(session?.organization.name ?? "");
  const [members, setMembers] = useState<Membership[]>([]);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [githubConnectors, setGithubConnectors] = useState<GitHubConnector[]>([]);
  const [ghName, setGhName] = useState("");
  const [ghMode, setGhMode] = useState<ScmMode>("mock");
  const [ghPat, setGhPat] = useState("");
  const [ghRepoMap, setGhRepoMap] = useState("checkout-api=acme/checkout-api");
  const [actionConnectors, setActionConnectors] = useState<ActionConnector[]>([]);
  const [actProvider, setActProvider] = useState<ActionProviderType>("jira");
  const [actName, setActName] = useState("");
  const [actMode, setActMode] = useState<"mock" | "live">("mock");
  const [actTargets, setActTargets] = useState("OPS, ENG");
  const [actBaseUrl, setActBaseUrl] = useState("");
  const [actCred, setActCred] = useState("");
  const [newIntName, setNewIntName] = useState("");
  const [newIntSim, setNewIntSim] = useState(true);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);
  const [statusNotice, setStatusNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const mems = await api.listMemberships();
      setMembers(mems);
      if (canReadIntegrations) {
        const [intList, ghList, actList] = await Promise.all([
          api.listIntegrations(),
          api.listGitHubConnectors(),
          api.listActionConnectors(),
        ]);
        setIntegrations(intList);
        setGithubConnectors(ghList);
        setActionConnectors(actList);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [canReadIntegrations]);

  useEffect(() => {
    if (session) {
      setOrgName(session.organization.name);
      void loadSettings();
    }
  }, [session, loadSettings]);

  const handleRenameOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setStatusNotice(null);
    try {
      await api.updateOrganization(orgName.trim());
      await refreshSession();
      setStatusNotice("Organization name updated.");
    } catch (err) {
      setError(err);
    }
  };

  const handleRoleChange = async (membershipId: number, role: Role) => {
    setError(null);
    try {
      await api.updateMembershipRole(membershipId, role);
      await loadSettings();
    } catch (err) {
      setError(err);
    }
  };

  const handleCreateIntegration = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setRevealedSecret(null);
    try {
      const created = await api.createIntegration(newIntName.trim(), newIntSim);
      setRevealedSecret(created.signing_secret);
      setNewIntName("");
      await loadSettings();
    } catch (err) {
      setError(err);
    }
  };

  const handleSimulate = async (id: number) => {
    setError(null);
    setStatusNotice(null);
    try {
      const res = await api.simulateWebhook(id, "high_error_rate", "firing");
      setStatusNotice(`Simulated alert queued (event #${res.event_ids.join(", ")})`);
    } catch (err) {
      setError(err);
    }
  };

  const handleCreateGitHub = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setStatusNotice(null);
    const service_repo_map: Record<string, string> = {};
    for (const pair of ghRepoMap.split(",")) {
      const [svc, repo] = pair.split("=").map((s) => s.trim());
      if (svc && repo) service_repo_map[svc] = repo;
    }
    try {
      await api.createGitHubConnector({
        name: ghName.trim(),
        mode: ghMode,
        auth_type: ghMode === "mock" ? "mock" : "pat",
        ...(ghMode === "live" && ghPat.trim() ? { credential: ghPat.trim() } : {}),
        service_repo_map,
      });
      setGhName("");
      setGhPat("");
      setStatusNotice("Read-only GitHub connector saved.");
      await loadSettings();
    } catch (err) {
      setError(err);
    }
  };

  const handleTestGitHub = async (id: number) => {
    setError(null);
    setStatusNotice(null);
    try {
      const res = await api.testGitHubConnector(id);
      setStatusNotice(
        `GitHub test (${res.mode === "mock" ? "DEMO/MOCK" : "LIVE"}): ${res.ok ? "OK" : "FAILED"} — ${res.diagnostics}`,
      );
      await loadSettings();
    } catch (err) {
      setError(err);
    }
  };

  return (
    <AppShell>
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Organization & Settings</h1>
        <p className="text-sm text-slate-500">
          Manage your organization, member roles, and Alertmanager webhook integrations.
        </p>
      </div>

      {error !== null && (
        <div className="mt-4">
          <ErrorAlert error={error} onRetry={loadSettings} />
        </div>
      )}
      {statusNotice && (
        <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-900">
          {statusNotice}
        </div>
      )}

      {loading ? (
        <div className="mt-6">
          <LoadingSkeleton rows={4} />
        </div>
      ) : (
        <div className="mt-6 space-y-6">
          {/* Organization */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Organization</h2>
            <form onSubmit={handleRenameOrg} className="mt-3 flex flex-col gap-3 sm:flex-row">
              <input
                aria-label="Organization name"
                disabled={!canUpdateOrg}
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:bg-slate-100"
              />
              <button
                type="submit"
                disabled={!canUpdateOrg}
                title={canUpdateOrg ? "Save organization name" : "Only Owners can rename the organization"}
                className="rounded-md bg-indigo-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                Save Name
              </button>
            </form>
            {!canUpdateOrg && (
              <p className="mt-1.5 text-xs text-slate-500">
                Only organization <code className="font-mono">owner</code> accounts can rename the
                organization.
              </p>
            )}
          </section>

          {/* Members */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Members & Roles</h2>
            <ul className="mt-3 divide-y divide-slate-100">
              {members.map((m) => (
                <li
                  key={m.id}
                  className="flex flex-col gap-2 py-2.5 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-900">{m.full_name}</p>
                    <p className="text-xs text-slate-500">{m.email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <RoleBadge role={m.role} />
                    {canManageMembers && (
                      <select
                        aria-label={`Change role for ${m.email}`}
                        value={m.role}
                        onChange={(e) => handleRoleChange(m.id, e.target.value as Role)}
                        className="rounded border border-slate-300 bg-white px-2 py-1 text-xs"
                      >
                        <option value="viewer">viewer</option>
                        <option value="engineer">engineer</option>
                        <option value="admin">admin</option>
                        <option value="owner">owner</option>
                      </select>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {/* Integrations */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Alertmanager Integrations</h2>
            {!canReadIntegrations ? (
              <p className="mt-2 text-xs text-slate-500">
                Integration configuration requires Admin or Owner role.
              </p>
            ) : (
              <>
                {revealedSecret && (
                  <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                    <p className="font-semibold">Signing secret (shown once):</p>
                    <code className="mt-1 block break-all font-mono">{revealedSecret}</code>
                  </div>
                )}

                <ul className="mt-3 space-y-2">
                  {integrations.map((cfg) => (
                    <li
                      key={cfg.id}
                      className="flex flex-col gap-2 rounded-md border border-slate-200 p-3 text-xs sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div>
                        <p className="font-semibold text-slate-900">
                          {cfg.name}{" "}
                          <span className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-700">
                            {cfg.connection_status}
                          </span>
                        </p>
                        <p className="mt-0.5 font-mono text-slate-500">{cfg.webhook_path}</p>
                      </div>
                      {canManageIntegrations && (
                        <button
                          type="button"
                          onClick={() => handleSimulate(cfg.id)}
                          className="rounded border border-indigo-300 bg-indigo-50 px-3 py-1.5 font-medium text-indigo-800 hover:bg-indigo-100"
                        >
                          Run Simulator Alert
                        </button>
                      )}
                    </li>
                  ))}
                </ul>

                {canManageIntegrations && (
                  <form
                    onSubmit={handleCreateIntegration}
                    className="mt-4 flex flex-col gap-2 border-t border-slate-100 pt-4 sm:flex-row sm:items-center"
                  >
                    <input
                      required
                      minLength={2}
                      value={newIntName}
                      onChange={(e) => setNewIntName(e.target.value)}
                      placeholder="New integration name"
                      className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                    />
                    <label className="flex items-center gap-1.5 text-xs text-slate-700">
                      <input
                        type="checkbox"
                        checked={newIntSim}
                        onChange={(e) => setNewIntSim(e.target.checked)}
                      />
                      Simulator mode
                    </label>
                    <button
                      type="submit"
                      className="rounded-md bg-slate-800 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-slate-900"
                    >
                      Add Integration
                    </button>
                  </form>
                )}
              </>
            )}
          </section>

          {/* Read-Only GitHub Evidence Connector */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">
              GitHub Read-Only Evidence Connector
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Read-only commits, PRs, reviews, and deployments. No repository write scope.
            </p>
            {!canReadIntegrations ? (
              <p className="mt-2 text-xs text-slate-500">
                Connector configuration requires Admin or Owner role.
              </p>
            ) : (
              <>
                <ul className="mt-3 space-y-2">
                  {githubConnectors.map((c) => (
                    <li
                      key={c.id}
                      className="flex flex-col gap-2 rounded-md border border-slate-200 p-3 text-xs sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-slate-900">{c.name}</span>
                          <span
                            className={`rounded px-1.5 py-0.5 font-mono font-semibold ${
                              c.mode === "mock"
                                ? "bg-violet-100 text-violet-800"
                                : "bg-emerald-100 text-emerald-800"
                            }`}
                          >
                            {c.mode === "mock" ? "DEMO / MOCK" : "LIVE"}
                          </span>
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-700">
                            test: {c.last_test_status}
                          </span>
                        </div>
                        <p className="mt-1 text-slate-500">
                          Repos: {JSON.stringify(c.service_repo_map)}
                          {c.last_success_at &&
                            ` · Last success: ${new Date(c.last_success_at).toLocaleString()}`}
                        </p>
                        {Object.keys(c.permission_summary).length > 0 && (
                          <p className="mt-0.5 font-mono text-slate-500">
                            Permissions: {JSON.stringify(c.permission_summary)}
                          </p>
                        )}
                        {c.last_error && <p className="mt-0.5 text-rose-700">{c.last_error}</p>}
                      </div>
                      {canManageIntegrations && (
                        <button
                          type="button"
                          onClick={() => handleTestGitHub(c.id)}
                          className="rounded border border-slate-300 bg-white px-3 py-1.5 font-medium text-slate-800 hover:bg-slate-50"
                        >
                          Test Connection
                        </button>
                      )}
                    </li>
                  ))}
                </ul>

                {canManageIntegrations && (
                  <form
                    onSubmit={handleCreateGitHub}
                    className="mt-4 grid grid-cols-1 gap-2 border-t border-slate-100 pt-4 sm:grid-cols-4"
                  >
                    <input
                      required
                      minLength={2}
                      value={ghName}
                      onChange={(e) => setGhName(e.target.value)}
                      placeholder="Connector name"
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                    />
                    <select
                      aria-label="GitHub connector mode"
                      value={ghMode}
                      onChange={(e) => setGhMode(e.target.value as ScmMode)}
                      className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm"
                    >
                      <option value="mock">DEMO / MOCK (no creds)</option>
                      <option value="live">LIVE (fine-grained PAT)</option>
                    </select>
                    <input
                      value={ghRepoMap}
                      onChange={(e) => setGhRepoMap(e.target.value)}
                      placeholder="service=owner/repo"
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                    />
                    <button
                      type="submit"
                      className="rounded-md bg-slate-800 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-slate-900"
                    >
                      Save Connector
                    </button>
                    {ghMode === "live" && (
                      <input
                        type="password"
                        required
                        value={ghPat}
                        onChange={(e) => setGhPat(e.target.value)}
                        placeholder="Fine-grained read-only PAT (encrypted at rest)"
                        className="rounded-md border border-slate-300 px-3 py-1.5 text-sm sm:col-span-4"
                      />
                    )}
                  </form>
                )}
              </>
            )}
          </section>

          {/* External Action Connectors (Jira & Slack, Phase 9) */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">
              External Action Connectors (Jira &amp; Slack — Human Approval Gate)
            </h2>
            <p className="mt-1 text-xs text-slate-600">
              Configure allowlisted Jira projects or Slack channels. Every write action requires
              explicit human approval before execution.
            </p>
            {!canReadIntegrations ? (
              <p className="mt-2 text-xs text-slate-500">
                Action connector configuration requires Admin or Owner role.
              </p>
            ) : (
              <>
                <ul className="mt-3 space-y-2">
                  {actionConnectors.map((ac) => (
                    <li
                      key={ac.id}
                      className="flex flex-col gap-2 rounded-md border border-slate-200 p-3 text-xs sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-slate-900">{ac.name}</span>
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] uppercase text-slate-700">
                            {ac.provider}
                          </span>
                          <span
                            className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ${
                              ac.mode === "live"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-violet-100 text-violet-800"
                            }`}
                          >
                            {ac.mode === "live" ? "LIVE" : "DEMO / MOCK"}
                          </span>
                          <span className="font-mono text-[11px] text-slate-500">
                            status: {ac.last_test_status}
                          </span>
                        </div>
                        <p className="font-mono text-[11px] text-slate-600">
                          Allowlisted targets: {ac.allowed_targets_json.join(", ")} · Scope:{" "}
                          {ac.permission_summary_json.scope ?? "narrow"}
                        </p>
                        {ac.last_error && (
                          <p className="text-[11px] text-rose-700">Last error: {ac.last_error}</p>
                        )}
                      </div>
                      {canManageIntegrations && (
                        <button
                          type="button"
                          onClick={async () => {
                            setError(null);
                            try {
                              const res = await api.testActionConnector(ac.id);
                              setStatusNotice(`${ac.name}: ${res.diagnostics}`);
                              await loadSettings();
                            } catch (err) {
                              setError(err);
                            }
                          }}
                          className="rounded border border-indigo-300 bg-indigo-50 px-3 py-1.5 font-medium text-indigo-800 hover:bg-indigo-100"
                        >
                          Test Connection
                        </button>
                      )}
                    </li>
                  ))}
                </ul>

                {canManageIntegrations && (
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      setError(null);
                      setStatusNotice(null);
                      try {
                        await api.createActionConnector({
                          provider: actProvider,
                          name: actName.trim(),
                          mode: actMode,
                          allowed_targets: actTargets
                            .split(",")
                            .map((s) => s.trim())
                            .filter(Boolean),
                          ...(actMode === "live" && actBaseUrl ? { base_url: actBaseUrl } : {}),
                          ...(actMode === "live" && actCred ? { credential: actCred } : {}),
                        });
                        setActName("");
                        setActCred("");
                        setStatusNotice("Action connector created.");
                        await loadSettings();
                      } catch (err) {
                        setError(err);
                      }
                    }}
                    className="mt-4 space-y-2 border-t border-slate-100 pt-4 text-xs"
                  >
                    <p className="font-semibold text-slate-800">Add Jira or Slack Action Connector</p>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
                      <select
                        aria-label="Action provider"
                        value={actProvider}
                        onChange={(e) => {
                          const p = e.target.value as ActionProviderType;
                          setActProvider(p);
                          setActTargets(p === "jira" ? "OPS, ENG" : "C01OPS, C02INCIDENTS");
                        }}
                        className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5"
                      >
                        <option value="jira">Jira (write:jira-work)</option>
                        <option value="slack">Slack (chat:write)</option>
                      </select>
                      <input
                        required
                        minLength={2}
                        placeholder="Connector name"
                        value={actName}
                        onChange={(e) => setActName(e.target.value)}
                        className="rounded-md border border-slate-300 px-2.5 py-1.5"
                      />
                      <select
                        aria-label="Action connector mode"
                        value={actMode}
                        onChange={(e) => setActMode(e.target.value as "mock" | "live")}
                        className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5"
                      >
                        <option value="mock">Demo / Mock Mode</option>
                        <option value="live">Live Mode</option>
                      </select>
                      <input
                        required
                        placeholder="Allowed projects / channels (comma-sep)"
                        value={actTargets}
                        onChange={(e) => setActTargets(e.target.value)}
                        className="rounded-md border border-slate-300 px-2.5 py-1.5"
                      />
                    </div>
                    {actMode === "live" && (
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        {actProvider === "jira" && (
                          <input
                            type="url"
                            required
                            placeholder="https://your-domain.atlassian.net"
                            value={actBaseUrl}
                            onChange={(e) => setActBaseUrl(e.target.value)}
                            className="rounded-md border border-slate-300 px-2.5 py-1.5"
                          />
                        )}
                        <input
                          type="password"
                          required
                          placeholder="Encrypted OAuth / Bot Token"
                          value={actCred}
                          onChange={(e) => setActCred(e.target.value)}
                          className="rounded-md border border-slate-300 px-2.5 py-1.5"
                        />
                      </div>
                    )}
                    <button
                      type="submit"
                      className="rounded-md bg-slate-800 px-3.5 py-1.5 font-medium text-white hover:bg-slate-900"
                    >
                      Save Action Connector
                    </button>
                  </form>
                )}
              </>
            )}
          </section>
        </div>
      )}
    </AppShell>
  );
}
