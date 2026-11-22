import fs from "node:fs";
import path from "node:path";
import { expect, test as setup } from "@playwright/test";

const AUTH_STATE_PATH = "playwright/.auth/admin.json";
const DEMO_EMAIL = process.env.E2E_DEMO_EMAIL ?? "admin@acme.local";
const DEMO_PASSWORD = process.env.E2E_DEMO_PASSWORD ?? "LocalDemoPassword123!";
const DEMO_ORG = process.env.E2E_DEMO_ORG ?? "acme-ops";

setup("authenticate demo admin once", async ({ page }) => {
  fs.mkdirSync(path.dirname(AUTH_STATE_PATH), { recursive: true });

  await page.goto("/login");
  await page.getByLabel("Email address").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill(DEMO_PASSWORD);
  const orgInput = page.getByLabel(/Organization slug/i);
  if (await orgInput.count()) {
    await orgInput.fill(DEMO_ORG);
  }
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByRole("heading", { name: "Operations Overview" })).toBeVisible({
    timeout: 15_000,
  });

  await page.context().storageState({ path: AUTH_STATE_PATH });
});
