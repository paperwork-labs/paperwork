/**
 * Regression: tab panels must not go blank after switching tabs (WS-76 PR-1).
 *
 * Run: cd apps/studio && pnpm exec playwright test admin-tabs --project=chromium
 */

import { test, expect, type Page } from "@playwright/test";

const PANEL_TIMEOUT_MS = 15_000;

async function waitForStudioTabShellHydrated(page: Page) {
  const shell = page.getByTestId("studio-page-tabs");
  await expect(shell).toBeVisible({ timeout: 25_000 });
  await expect(shell).toHaveAttribute("data-tabs-client-mounted", "1", { timeout: 25_000 });
}

/** Radix only exposes one visible tabpanel at a time (others use `hidden`). */
function activeTabPanel(page: Page) {
  return page.locator('[role="tabpanel"]:not([hidden])');
}

async function expectActivePanelContains(page: Page, pattern: RegExp | string) {
  const panel = activeTabPanel(page);
  await panel.waitFor({ state: "visible", timeout: PANEL_TIMEOUT_MS });
  const locator =
    typeof pattern === "string"
      ? panel.getByText(pattern, { exact: false })
      : panel.getByText(pattern);
  await locator.first().waitFor({ state: "visible", timeout: PANEL_TIMEOUT_MS });
}

test.describe("/admin/architecture — tab panels stay populated", () => {
  test("each tab shows content after click", async ({ page }) => {
    const resp = await page.goto("/admin/architecture?tab=overview", { waitUntil: "domcontentloaded" });
    if (!resp || resp.status() === 404) {
      test.skip();
      return;
    }

    await waitForStudioTabShellHydrated(page);
    await expectActivePanelContains(page, /command centre|Command centre/i);

    await page.getByRole("tab", { name: "Analytics" }).click();
    await expect(page).toHaveURL(/tab=analytics/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /PostHog visibility/);

    await page.getByRole("tab", { name: "Flows" }).click();
    await expect(page).toHaveURL(/tab=flows/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /n8n wiring/);

    await page.getByRole("tab", { name: "Data Sources" }).click();
    await expect(page).toHaveURL(/tab=data-sources/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /Decommissioned|Slack \(Brain\)/);
  });
});

test.describe("/admin/infrastructure — tab panels stay populated", () => {
  test("each tab shows content after click", async ({ page }) => {
    const resp = await page.goto("/admin/infrastructure?tab=services", { waitUntil: "domcontentloaded" });
    if (!resp || resp.status() === 404) {
      test.skip();
      return;
    }

    await waitForStudioTabShellHydrated(page);
    await expectActivePanelContains(page, /Deploy platform|Render:|Vercel:/i);

    await page.getByRole("tab", { name: "Secrets" }).click();
    await expect(page).toHaveURL(/tab=secrets/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /Secrets Vault|DATABASE_URL not set|Database connection failed/i);

    await page.getByRole("tab", { name: "Services" }).click();
    await expect(page).toHaveURL(/tab=services/, { timeout: PANEL_TIMEOUT_MS });
    await page.getByTestId("infra-inner-view-logs").click();
    await expect(page).toHaveURL(/infraView=logs/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /Application Logs|Brain-owned log store/i);

    await page.getByRole("tab", { name: "Cost" }).click();
    await expect(page).toHaveURL(/tab=cost/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /WS-74/i);
  });
});

test.describe("/admin/brain/personas — tab panels stay populated", () => {
  test("each tab shows content after click", async ({ page }) => {
    const resp = await page.goto("/admin/brain/personas?tab=registry", { waitUntil: "domcontentloaded" });
    if (!resp || resp.status() === 404 || resp.status() >= 500) {
      test.skip();
      return;
    }

    await expect(page).toHaveURL(/\/admin\/people/, { timeout: 15_000 });
    await expect(page).toHaveURL(/view=workspace/, { timeout: 15_000 });

    await waitForStudioTabShellHydrated(page);
    await expectActivePanelContains(page, /Persona id/);

    await page.getByRole("tab", { name: "Cost" }).click();
    await expect(page).toHaveURL(/tab=cost/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /Dispatches 7d/);

    await page.getByRole("tab", { name: "Routing" }).click();
    await expect(page).toHaveURL(/tab=routing/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /ea\.mdc|EA routing/i);

    await page.getByRole("tab", { name: /activity stream/i }).click();
    await expect(page).toHaveURL(/tab=activity/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /agent_dispatch_log\.json/);

    await page.getByRole("tab", { name: /promotions queue/i }).click();
    await expect(page).toHaveURL(/tab=promotions-queue/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /self_merge_promotions\.json/);

    await page.getByRole("tab", { name: /open roles/i }).click();
    await expect(page).toHaveURL(/tab=open-roles/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /Model Assignment|No open roles|\.cursor\/rules/);

    await page.getByRole("tab", { name: /model registry/i }).click();
    await expect(page).toHaveURL(/tab=model-registry/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /AI_MODEL_REGISTRY\.md/);
  });
});

test.describe("/admin/brain/self-improvement — tab panels stay populated", () => {
  test("each tab shows content after click", async ({ page }) => {
    const resp = await page.goto("/admin/brain/self-improvement?tab=learning", {
      waitUntil: "domcontentloaded",
    });
    if (!resp || resp.status() === 404) {
      test.skip();
      return;
    }

    await waitForStudioTabShellHydrated(page);
    await expectActivePanelContains(page, /Volume by model|Dispatches \(7d\)/);

    await page.getByRole("tab", { name: "Promotions" }).click();
    await expect(page).toHaveURL(/tab=promotions/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /Current tier|Clean merges|self_merge_promotions/i);

    await page.getByRole("tab", { name: "Outcomes" }).click();
    await expect(page).toHaveURL(/tab=outcomes/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /Merged/);

    await page.getByRole("tab", { name: "Retros" }).click();
    await expect(page).toHaveURL(/tab=retros/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /weekly_retros|Retros array/i);

    await page.getByRole("tab", { name: "Automation" }).click();
    await expect(page).toHaveURL(/tab=automation-state/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /Schedules parsed statically/);

    await page.getByRole("tab", { name: "Procedural memory" }).click();
    await expect(page).toHaveURL(/tab=procedural-memory/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /procedural_memory\.yaml/);

    await page.getByRole("tab", { name: "Audits" }).click();
    await expect(page).toHaveURL(/tab=audits/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /BRAIN_API_URL|Filter:|weekly/);

    await page.getByRole("tab", { name: "Index" }).click();
    await expect(page).toHaveURL(/tab=index/, { timeout: PANEL_TIMEOUT_MS });
    await expectActivePanelContains(page, /Composite score uses the same weights/);
  });
});
