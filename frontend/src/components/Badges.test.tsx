import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SeverityBadge, SimulatedBadge, StatusBadge } from "./Badges";
import { canTransition, hasPermission } from "@/lib/rbac";

describe("Badges and RBAC helpers", () => {
  it("renders severity, status, and simulated badges", () => {
    render(
      <div>
        <SeverityBadge severity="critical" />
        <StatusBadge status="acknowledged" />
        <SimulatedBadge />
      </div>,
    );
    expect(screen.getByText("critical")).toBeInTheDocument();
    expect(screen.getByText("acknowledged")).toBeInTheDocument();
    expect(screen.getByText("Simulated")).toBeInTheDocument();
  });

  it("enforces role permissions and valid state transitions", () => {
    expect(hasPermission("viewer", "incident:read")).toBe(true);
    expect(hasPermission("viewer", "incident:write")).toBe(false);
    expect(hasPermission("engineer", "incident:write")).toBe(true);
    expect(hasPermission("engineer", "incident:archive")).toBe(false);
    expect(hasPermission("admin", "event:replay")).toBe(true);

    expect(canTransition("open", "acknowledged")).toBe(true);
    expect(canTransition("closed", "resolved")).toBe(false);
    expect(canTransition("closed", "open")).toBe(true);
  });
});
