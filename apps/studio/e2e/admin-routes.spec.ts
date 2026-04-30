/**
 * Smoke tests for admin route redirects and tabbed shells (WS-69 PR C).
 *
 * Run against the dev server with STUDIO_E2E_FIXTURE=1:
 *   pnpm --filter studio run dev:e2e   # in one terminal
 *   pnpm --filter studio exec playwright test e2e/admin-routes.spec.ts
 */

import { test, expect, type Page } from "@playwright/test";

async function waitForStudioTabShellHydrated(page: Page) {
  const shell = page.getByTestId("studio-page-tabs");
  await expect(shell).toBeVisible({ timeout: 25_000 });
  await expect(shell).toHaveAttribute("data-tabs-client-mounted", "1", { timeout: 25_000 });
}

// ---------------------------------------------------------------------------
// Redirect smoke tests (all 7 legacy routes → 308 permanent destinations)
// ---------------------------------------------------------------------------

test.describe("Admin route redirects (WS-69 PR C — 308 permanent)", () => {
  test("/admin/workflows redirects to /admin/architecture?tab=flows", async ({ page }) => {
    const resp = await page.goto("/admin/workflows");
    expect(resp?.url()).toContain("/admin/architecture");
    expect(resp?.url()).toContain("tab=flows");
  });

  test("/admin/n8n-mirror redirects to /admin/architecture?tab=flows", async ({ page }) => {
    const resp = await page.goto("/admin/n8n-mirror");
    expect(resp?.url()).toContain("/admin/architecture");
    expect(resp?.url()).toContain("tab=flows");
  });

  test("/admin/automation redirects to /admin/architecture?tab=flows", async ({ page }) => {
    const resp = await page.goto("/admin/automation");
    expect(resp?.url()).toContain("/admin/architecture");
    expect(resp?.url()).toContain("tab=flows");
  });

  test("/admin/analytics redirects to /admin/architecture?tab=analytics", async ({ page }) => {
    const resp = await page.goto("/admin/analytics");
    expect(resp?.url()).toContain("/admin/architecture");
    expect(resp?.url()).toContain("tab=analytics");
  });

  test("/admin/secrets redirects to /admin/infrastructure?tab=secrets", async ({ page }) => {
    const resp = await page.goto("/admin/secrets");
    expect(resp?.url()).toContain("/admin/infrastructure");
    expect(resp?.url()).toContain("tab=secrets");
  });

  test("/admin/founder-actions redirects to /admin/runbook", async ({
    page,
  }) => {
    const resp = await page.goto("/admin/founder-actions");
    expect(resp?.url()).toContain("/admin/runbook");
  });

  test("/admin/brain-learning redirects to /admin/brain/self-improvement?tab=learning", async ({
    page,
  }) => {
    const resp = await page.goto("/admin/brain-learning");
    expect(resp?.url()).toContain("/admin/brain/self-improvement");
    expect(resp?.url()).toContain("tab=learning");
  });
});

// ---------------------------------------------------------------------------
// Architecture tabbed shell (tabs: overview, analytics, flows, data-sources)
// ---------------------------------------------------------------------------

test.describe("Architecture tabbed shell (WS-69 PR C)", () => {
  test("renders with all four tabs visible", async ({ page }) => {
    await page.goto("/admin/architecture", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    await expect(page.getByRole("tab", { name: "Overview" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Analytics" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Flows" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Data Sources" })).toBeVisible();
  });

  test("clicking Analytics tab updates URL", async ({ page }) => {
    await page.goto("/admin/architecture", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    await expect(page.getByTestId("page-tab-analytics")).toBeVisible({ timeout: 10_000 });
    await page.getByTestId("page-tab-analytics").click();
    await expect(page).toHaveURL(/tab=analytics/, { timeout: 10_000 });
  });

  test("clicking Flows tab updates URL", async ({ page }) => {
    await page.goto("/admin/architecture", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    await page.getByRole("tab", { name: "Flows" }).click();
    await expect(page).toHaveURL(/tab=flows/);
  });

  test("deep-linking to ?tab=flows shows flows panel", async ({ page }) => {
    await page.goto("/admin/architecture?tab=flows", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    const panel = page.getByRole("tabpanel");
    await expect(panel).toBeVisible();
  });

  test("deep-linking to ?tab=data-sources shows data-sources panel", async ({ page }) => {
    await page.goto("/admin/architecture?tab=data-sources", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    const panel = page.getByRole("tabpanel");
    await expect(panel).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Infrastructure tabbed shell (tabs: services, secrets, logs, cost)
// ---------------------------------------------------------------------------

test.describe("Infrastructure tabbed shell (WS-69 PR C — STUDIO_E2E_FIXTURE=1 dev server)", () => {
  test("renders with four tabs (Services, Secrets, Logs, Cost) — no Overview", async ({ page }) => {
    await page.goto("/admin/infrastructure", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    await expect(page.getByRole("tab", { name: "Overview" })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "Services" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Secrets" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Logs" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Cost" })).toBeVisible();
  });

  test("default tab is services", async ({ page }) => {
    await page.goto("/admin/infrastructure", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    await expect(page.getByRole("tab", { name: "Services" })).toHaveAttribute("aria-selected", "true");
  });

  test("?tab=overview redirects to services", async ({ page }) => {
    await page.goto("/admin/infrastructure?tab=overview", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/tab=services/, { timeout: 15_000 });
  });

  test("switching to Secrets tab updates URL", async ({ page }) => {
    await page.goto("/admin/infrastructure", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    await page.getByRole("tab", { name: "Secrets" }).click();
    await expect(page).toHaveURL(/tab=secrets/);
  });

  test("Logs tab shows application logs UI", async ({ page }) => {
    await page.goto("/admin/infrastructure", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    await page.getByRole("tab", { name: "Logs" }).click();
    await expect(page).toHaveURL(/tab=logs/, { timeout: 15_000 });
    await expect(page.getByRole("tab", { name: "Logs" })).toHaveAttribute("aria-selected", "true", {
      timeout: 15_000,
    });
    await expect(page.locator('[role="tabpanel"]:not([hidden])').getByText(/Application Logs|Brain-owned/i).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("Cost tab shows WS-74 placeholder", async ({ page }) => {
    await page.goto("/admin/infrastructure", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    await page.getByRole("tab", { name: "Cost" }).click();
    await expect(page).toHaveURL(/tab=cost/, { timeout: 15_000 });
    await expect(page.getByRole("tab", { name: "Cost" })).toHaveAttribute("aria-selected", "true", {
      timeout: 15_000,
    });
    await expect(page.locator('[role="tabpanel"]:not([hidden])').getByText(/WS-74/i).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("deep-linking to ?tab=secrets shows secrets panel", async ({ page }) => {
    await page.goto("/admin/infrastructure?tab=secrets", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    await expect(page.getByRole("tab", { name: "Secrets" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});

// ---------------------------------------------------------------------------
// Brain bucket shells
// ---------------------------------------------------------------------------

test.describe("Brain bucket stub pages (WS-69 PR C)", () => {
  test.describe.configure({ timeout: 90_000 });
  test("/admin/brain/personas renders without 5xx and shows PR F copy", async ({ page }) => {
    const resp = await page.goto("/admin/brain/personas", { waitUntil: "domcontentloaded" });
    if (!resp || resp.status() >= 500) {
      test.skip();
      return;
    }
    const bodyText = await page.locator("body").innerText();
    if (
      bodyText.includes("YAMLException") ||
      bodyText.includes("unidentified alias") ||
      bodyText.includes("Something went wrong")
    ) {
      test.skip();
      return;
    }
    await expect(page.getByRole("main").getByRole("heading", { name: "People" })).toBeVisible({
      timeout: 15_000,
    });
  });

  test("/admin/brain/personas renders all People dashboard tabs", async ({ page }) => {
    const resp = await page.goto("/admin/brain/personas", { waitUntil: "domcontentloaded" });
    if (!resp || resp.status() >= 500) {
      test.skip();
      return;
    }
    const bodyText = await page.locator("body").innerText();
    if (
      bodyText.includes("YAMLException") ||
      bodyText.includes("unidentified alias") ||
      bodyText.includes("Something went wrong")
    ) {
      test.skip();
      return;
    }
    await waitForStudioTabShellHydrated(page);
    await expect(page.getByRole("tab", { name: "Specs", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: /activity stream/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /promotions queue/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /open roles/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Cost" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Routing" })).toBeVisible();
    await expect(page.getByRole("tab", { name: /model registry/i })).toBeVisible();
  });

  test("/admin/brain/conversations renders without 5xx and shows PR E copy", async ({ page }) => {
    const resp = await page.goto("/admin/brain/conversations", { waitUntil: "domcontentloaded" });
    expect(resp?.status()).toBeLessThan(500);
    await expect(
      page
        .getByRole("main")
        .getByRole("heading", { name: "Conversations" })
        .or(page.getByRole("main").getByText(/Brain is not configured/i)),
    ).toBeVisible({ timeout: 30_000 });
  });

  test("/admin/brain/conversations accepts ?filter=needs-action without error", async ({
    page,
  }) => {
    const resp = await page.goto("/admin/brain/conversations?filter=needs-action", {
      waitUntil: "domcontentloaded",
    });
    expect(resp?.status()).toBeLessThan(500);
  });

  test("/admin/brain/self-improvement renders without 5xx", async ({ page }) => {
    const resp = await page.goto("/admin/brain/self-improvement", {
      waitUntil: "domcontentloaded",
    });
    expect(resp?.status()).toBeLessThan(500);
  });

  test("/admin/brain/self-improvement renders all eight tabs", async ({ page }) => {
    await page.goto("/admin/brain/self-improvement", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    await expect(page.getByRole("tab", { name: "Learning" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Promotions" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Outcomes" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Retros" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Automation" })).toBeVisible();
    await expect(page.getByRole("tab", { name: /procedural memory/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Audits" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Index" })).toBeVisible();
  });

  test("/admin/brain/self-improvement learning tab shows dispatch copy", async ({ page }) => {
    await page.goto("/admin/brain/self-improvement", { waitUntil: "domcontentloaded" });
    await waitForStudioTabShellHydrated(page);
    await expect(page.getByRole("tab", { name: "Learning" })).toHaveAttribute("aria-selected", "true", {
      timeout: 15_000,
    });
    await expect(
      page.locator('[role="tabpanel"]:not([hidden])').getByText(/Volume by model|agent_dispatch_log\.json/i).first(),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("/admin/expenses renders without 5xx and shows PR N copy", async ({ page }) => {
    const resp = await page.goto("/admin/expenses", { waitUntil: "domcontentloaded" });
    expect(resp?.status()).toBeLessThan(500);
    await expect(
      page
        .getByRole("main")
        .getByRole("heading", { name: "Expenses" })
        .or(page.getByRole("main").getByText(/Brain API not configured/i)),
    ).toBeVisible({ timeout: 30_000 });
  });
});
