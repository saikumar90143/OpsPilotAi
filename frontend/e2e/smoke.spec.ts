import { expect, test } from "@playwright/test";

const DEMO_EMAIL = process.env.E2E_DEMO_EMAIL ?? "admin@acme.local";
const DEMO_PASSWORD = process.env.E2E_DEMO_PASSWORD ?? "LocalDemoPassword123!";

test("login, view incidents, filter, open detail, and acknowledge", async ({ page, isMobile }) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByRole("heading", { name: "Operations Overview" })).toBeVisible();

  if (isMobile) {
    await page.getByRole("button", { name: "Open navigation menu" }).click();
  }
  await page.getByRole("link", { name: "Incidents", exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "Incidents" })).toBeVisible();

  await page.getByLabel("Search incidents").fill("Checkout");
  const firstIncident = page.locator("ul li a").first();
  await expect(firstIncident).toBeVisible();
  await firstIncident.click();

  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const ackButton = page.getByRole("button", { name: "Acknowledge" });
  if (await ackButton.isEnabled()) {
    await ackButton.click();
  }
  await expect(page.getByText("acknowledged", { exact: true })).toBeVisible();
});
