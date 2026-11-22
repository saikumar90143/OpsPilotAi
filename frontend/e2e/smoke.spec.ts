import { expect, test, type Page } from "@playwright/test";

const diagnosticsMap = new WeakMap<Page, string[]>();

async function navigateViaMenu(page: Page, linkName: string, isMobile: boolean) {
  if (isMobile) {
    await page.getByRole("button", { name: "Open navigation menu" }).click();
  }
  await page.getByRole("link", { name: linkName, exact: true }).first().click();
}

test.beforeEach(async ({ page }) => {
  const entries: string[] = [];
  diagnosticsMap.set(page, entries);

  page.on("pageerror", (err) => {
    entries.push(`[pageerror] ${err.message}`);
  });
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      entries.push(`[console.error] ${msg.text()}`);
    }
  });
  page.on("requestfailed", (req) => {
    entries.push(`[requestfailed] ${req.method()} ${req.url()} - ${req.failure()?.errorText ?? "failed"}`);
  });
  page.on("response", (res) => {
    if (res.status() >= 500) {
      entries.push(`[http ${res.status()}] ${res.request().method()} ${res.url()}`);
    }
  });
});

test.afterEach(async ({ page }, testInfo) => {
  const entries = diagnosticsMap.get(page) ?? [];
  if (testInfo.status !== testInfo.expectedStatus && entries.length > 0) {
    await testInfo.attach("browser-diagnostics.txt", {
      body: entries.join("\n"),
      contentType: "text/plain",
    });
  }
});

test("overview, create deterministic incident, acknowledge, and run read-only AI investigation", async ({
  page,
  isMobile,
}, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Operations Overview" })).toBeVisible();
  await expect(page.getByText("Total in Window")).toBeVisible();

  await navigateViaMenu(page, "Incidents", isMobile);
  await expect(page.getByRole("heading", { name: "Incidents" })).toBeVisible();

  const uniqueTitle = `E2E Smoke ${testInfo.project.name} ${Date.now()}`;
  await page.getByRole("button", { name: /New Incident/i }).click();
  await expect(page.getByRole("heading", { name: "Create Incident" })).toBeVisible();
  await page.locator("#new-title").fill(uniqueTitle);
  await page.locator("#new-service").fill("e2e-smoke-svc");
  await page.getByRole("button", { name: "Create", exact: true }).click();

  await expect(page.getByRole("heading", { name: "Create Incident" })).toBeHidden();
  await page.getByLabel("Search incidents").fill(uniqueTitle);

  const targetIncident = page.locator("ul li a").filter({ hasText: uniqueTitle }).first();
  await expect(targetIncident).toBeVisible({ timeout: 10_000 });
  await targetIncident.click();

  await expect(page.getByRole("heading", { level: 1, name: uniqueTitle })).toBeVisible();

  const ackButton = page.getByRole("button", { name: "Acknowledge", exact: true });
  await expect(ackButton).toBeEnabled();
  await ackButton.click();
  await expect(page.getByText(/^acknowledged$/i).first()).toBeVisible({ timeout: 10_000 });
  await expect(ackButton).toBeDisabled();

  // Verify AI Investigation Copilot UI availability (honest mock mode) and execute a real read-only run
  await expect(page.getByRole("heading", { name: /AI Investigation Copilot/i })).toBeVisible();
  await expect(page.getByText("MOCK / DETERMINISTIC")).toBeVisible();

  const startAiButton = page.getByRole("button", { name: "Start Read-Only Investigation" });
  await expect(startAiButton).toBeEnabled();
  await startAiButton.click();

  await expect(page.getByText("COMPLETED")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("APPROVED TOOL ACTIVITY")).toBeVisible();
  await expect(page.getByText("Observed Facts", { exact: true })).toBeVisible();
});

test("navigate and verify live UI across events, evidence & KB, actions, and settings", async ({
  page,
  isMobile,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Operations Overview" })).toBeVisible();

  await navigateViaMenu(page, "Ingestion & Events", isMobile);
  await expect(page.getByRole("heading", { name: "Ingestion & Failed Events" })).toBeVisible();

  await navigateViaMenu(page, "Evidence & KB", isMobile);
  await expect(
    page.getByRole("heading", { name: "Evidence & Engineering Knowledge Base" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Knowledge Base/i }).click();
  await expect(page.getByRole("heading", { name: "Hybrid Knowledge Base Search" })).toBeVisible();

  await navigateViaMenu(page, "Action Approvals", isMobile);
  await expect(
    page.getByRole("heading", { name: "External Action Approvals (Human Gate)" }),
  ).toBeVisible();

  await navigateViaMenu(page, "Settings", isMobile);
  await expect(page.getByRole("heading", { name: "Organization & Settings" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Alertmanager Integrations" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /External Action Connectors/i }),
  ).toBeVisible();
});
