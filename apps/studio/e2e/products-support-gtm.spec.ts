/**
 * Product cockpit support inbox + GTM tab (WS-76 PR-24ab).
 * Run with STUDIO_E2E_FIXTURE=1 (`webServer` in playwright.config uses `pnpm run dev:e2e`).
 */

import { expect, test, type Page } from "@playwright/test";

async function waitForTabShell(page: Page) {
  const shell = page.getByTestId("studio-page-tabs");
  await expect(shell).toBeVisible({ timeout: 60_000 });
  await expect(shell).toHaveAttribute("data-tabs-client-mounted", "1", { timeout: 30_000 });
}

test.describe("Product Support + GTM (WS-76 PR-24ab — STUDIO_E2E_FIXTURE=1)", () => {
  test.describe.configure({ timeout: 120_000 });

  test("Support tab lists AxiomFolio tickets", async ({ page }) => {
    await page.goto("/admin/products/axiomfolio?tab=support", { waitUntil: "domcontentloaded" });
    await waitForTabShell(page);
    await page.getByTestId("page-tab-support").click();
    const inbox = page.getByTestId("product-support-inbox");
    await expect(inbox).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("support-ticket-row")).toHaveCount(3);
    await expect(page.getByText("Question about Pro tier billing")).toBeVisible();
    await expect(page.getByText("Feature request: custom benchmark")).toBeVisible();
  });

  test("GTM tab shows rollup stats and product rows", async ({ page }) => {
    await page.goto("/admin/products?tab=gtm", { waitUntil: "domcontentloaded" });
    await waitForTabShell(page);
    await page.getByTestId("page-tab-gtm").click();
    await expect(page.getByTestId("page-tab-gtm")).toBeVisible();
    await expect(page.getByTestId("product-gtm-surface")).toBeVisible();
    await expect(page.getByTestId("hq-stat-card").filter({ hasText: "Total visitors" })).toBeVisible();
    await expect(page.getByTestId("hq-stat-card").filter({ hasText: "Total signups" })).toBeVisible();
    const n = await page.getByTestId("gtm-product-row").count();
    expect(n).toBeGreaterThan(0);
    await expect(page.getByTestId("gtm-product-row").filter({ hasText: "AxiomFolio" })).toBeVisible();
  });
});
