import { describe, expect, it, vi, beforeEach } from "vitest";
import { api, ApiClientError } from "./api";

describe("api client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    Object.defineProperty(document, "cookie", {
      writable: true,
      value: "opspilot_csrf=csrf-token-123",
    });
  });

  it("sends credentials: include and X-CSRF-Token on state-changing requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 1 }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.createIncident({
      title: "Test incident",
      description: "",
      service: "api",
      environment: "production",
      severity: "high",
      tags: [],
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe("include");
    const headers = init.headers as Headers;
    expect(headers.get("X-CSRF-Token")).toBe("csrf-token-123");
  });

  it("throws ApiClientError with backend error code and request_id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ error: "not_found", message: "Incident not found", request_id: "req-9" }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getIncident(999)).rejects.toMatchObject({
      name: "ApiClientError",
      status: 404,
      code: "not_found",
      requestId: "req-9",
    } satisfies Partial<ApiClientError>);
  });
});
