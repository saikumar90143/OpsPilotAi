import type { Metadata } from "next";
import { ErrorBoundary } from "@/components/Feedback";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpsPilot AI — Incident Operations",
  description: "Multi-tenant incident investigation and operations dashboard.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ErrorBoundary>
          <AuthProvider>{children}</AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
