"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { ErrorAlert } from "@/components/Feedback";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { session, loading, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!loading && session) {
      router.replace("/");
    }
  }, [loading, session, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password, orgSlug.trim() || undefined);
      router.replace("/");
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900 px-4 py-12">
      <div className="w-full max-w-md rounded-xl border border-slate-800 bg-white p-8 shadow-xl">
        <div className="flex items-center gap-2.5">
          <ShieldCheck className="h-7 w-7 text-indigo-600" aria-hidden="true" />
          <div>
            <h1 className="text-lg font-semibold text-slate-900">OpsPilot AI</h1>
            <p className="text-xs text-slate-500">Sign in to your organization workspace</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {error !== null && <ErrorAlert error={error} />}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700">
              Email address
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@acme.local"
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900"
            />
          </div>

          <div>
            <label htmlFor="orgSlug" className="block text-sm font-medium text-slate-700">
              Organization slug <span className="font-normal text-slate-400">(optional)</span>
            </label>
            <input
              id="orgSlug"
              name="orgSlug"
              type="text"
              value={orgSlug}
              onChange={(e) => setOrgSlug(e.target.value)}
              placeholder="acme-ops"
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="mt-5 rounded-md bg-slate-50 p-3 text-xs text-slate-600">
          Sessions use <code className="font-mono">HttpOnly</code> cookies and CSRF protection. For
          local demo accounts, run <code className="font-mono">python -m app.bootstrap</code> in{" "}
          <code className="font-mono">backend/</code>.
        </p>
      </div>
    </div>
  );
}
