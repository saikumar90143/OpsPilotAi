"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  BookOpen,
  CheckSquare,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { RoleBadge } from "./Badges";
import { LoadingSkeleton } from "./Feedback";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/incidents", label: "Incidents", icon: AlertCircle },
  { href: "/actions", label: "Action Approvals", icon: CheckSquare },
  { href: "/evidence", label: "Evidence & KB", icon: BookOpen },
  { href: "/events", label: "Ingestion & Events", icon: Activity },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { session, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!loading && !session) {
      router.replace("/login");
    }
  }, [loading, session, router]);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl p-8">
        <LoadingSkeleton rows={5} />
      </div>
    );
  }

  if (!session) {
    return null;
  }

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  const navContent = (
    <div className="flex h-full flex-col justify-between bg-slate-900 px-3 py-5 text-slate-200">
      <div>
        <div className="flex items-center gap-2.5 px-3 pb-5">
          <ShieldCheck className="h-6 w-6 text-indigo-400" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold tracking-tight text-white">OpsPilot AI</p>
            <p className="text-xs text-slate-400">{session.organization.name}</p>
          </div>
        </div>
        <nav aria-label="Primary navigation" className="space-y-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-indigo-600 text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="border-t border-slate-800 pt-4">
        <div className="px-3 pb-3">
          <p className="truncate text-xs font-medium text-white">{session.user.full_name}</p>
          <p className="truncate text-xs text-slate-400">{session.user.email}</p>
          <div className="mt-2">
            <RoleBadge role={session.role} />
          </div>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          <span>Sign out</span>
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-indigo-600 focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        {navContent}
      </aside>

      {/* Mobile header */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-indigo-600" aria-hidden="true" />
          <span className="text-sm font-semibold text-slate-900">OpsPilot AI</span>
        </div>
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          aria-label="Open navigation menu"
          className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100"
        >
          <Menu className="h-5 w-5" aria-hidden="true" />
        </button>
      </header>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden" role="dialog" aria-modal="true">
          <div
            className="fixed inset-0 bg-slate-900/50"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <div className="relative flex w-64 max-w-xs flex-1 flex-col">
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation menu"
              className="absolute right-3 top-4 rounded-md p-1 text-slate-400 hover:text-white"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
            {navContent}
          </div>
        </div>
      )}

      <main id="main-content" className="lg:pl-64">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">{children}</div>
      </main>
    </div>
  );
}
