"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, ApiClientError } from "./api";
import { hasPermission, type Permission } from "./rbac";
import type { AuthSession } from "./types";

interface AuthContextValue {
  session: AuthSession | null;
  loading: boolean;
  login: (email: string, password: string, orgSlug?: string) => Promise<AuthSession>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  can: (permission: Permission) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshSession = useCallback(async () => {
    try {
      const current = await api.me();
      setSession(current);
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 401) {
        setSession(null);
      } else {
        setSession(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  const login = useCallback(async (email: string, password: string, orgSlug?: string) => {
    const next = await api.login(email, password, orgSlug);
    setSession(next);
    return next;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setSession(null);
    }
  }, []);

  const can = useCallback(
    (permission: Permission) => hasPermission(session?.role, permission),
    [session?.role],
  );

  return (
    <AuthContext.Provider value={{ session, loading, login, logout, refreshSession, can }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
