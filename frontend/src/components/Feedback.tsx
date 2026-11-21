"use client";

import React from "react";
import { AlertTriangle, Inbox } from "lucide-react";
import { ApiClientError } from "@/lib/api";

export function ErrorAlert({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message =
    error instanceof Error ? error.message : "An unexpected error occurred.";
  const requestId = error instanceof ApiClientError ? error.requestId : null;

  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-start gap-2.5">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" aria-hidden="true" />
        <div>
          <p className="font-medium">{message}</p>
          {requestId && requestId !== "-" && (
            <p className="mt-0.5 font-mono text-xs text-rose-700">Request ID: {requestId}</p>
          )}
        </div>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="self-start rounded-md border border-rose-300 bg-white px-3 py-1.5 text-xs font-medium text-rose-800 hover:bg-rose-100 sm:self-auto"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      <Inbox className="h-8 w-8 text-slate-400" aria-hidden="true" />
      <h3 className="mt-3 text-sm font-semibold text-slate-900">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-slate-500">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function LoadingSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading content">
      {Array.from({ length: rows }).map((_, idx) => (
        <div
          key={idx}
          className="h-14 animate-pulse rounded-lg border border-slate-200 bg-slate-100"
        />
      ))}
    </div>
  );
}

interface ErrorBoundaryState {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, message: error.message || "Unexpected rendering error" };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="mx-auto max-w-lg p-6">
          <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-5">
            <h2 className="text-base font-semibold text-rose-900">Something went wrong</h2>
            <p className="mt-1 text-sm text-rose-800">{this.state.message}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-4 rounded-md bg-rose-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-800"
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
