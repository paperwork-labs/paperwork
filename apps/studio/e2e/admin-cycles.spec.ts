/**
 * Cycles board on Sprints (WS-76 PR-17).
 *
 * Run: cd apps/studio && pnpm exec playwright test e2e/admin-cycles.spec.ts --project=chromium
 */

import { test, expect, type Page } from "@playwright/test";

async function waitForStudioTabShellHydrated(page: Page) {
  const shell = page.getByTestId("studio-page-tabs");
  await expect(shell).toBeVisible({ timeout: 25_000 });
  await expect(shell).toHaveAttribute("data-tabs-client-mounted", "1", { timeout: 25_000 });
}

test.describe("/admin/sprints — Cycles tab", () => {
  test("shows three columns and at least one workstream card", async ({ page }) => {
    const resp = await page.goto("/admin/sprints", { waitUntil: "domcontentloaded" });
    if (!resp || resp.status() === 404) {
      test.skip();
      return;
    }

    await waitForStudioTabShellHydrated(page);

    await page.getByRole("tab", { name: "Cycles" }).click();
    await expect(page).toHaveURL(/tab=cycles/, { timeout: 15_000 });

    await expect(page.getByTestId("cycles-column-active")).toBeVisible();
    await expect(page.getByTestId("cycles-column-backlog")).toBeVisible();
    await expect(page.getByTestId("cycles-column-done")).toBeVisible();

    await expect(page.getByTestId("workstream-cycle-card").first()).toBeVisible({
      timeout: 15_000,
    });
  });
});
