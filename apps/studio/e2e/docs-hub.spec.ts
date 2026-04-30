/**
 * Docs hub IA (WS-76 PR-19b): category filters and card grid.
 *
 * Run: pnpm --filter @paperwork-labs/studio exec playwright test e2e/docs-hub.spec.ts
 */

import { expect, test } from "@playwright/test";

test.describe("Docs hub filters", () => {
  test("Philosophy filter hides a runbook doc", async ({ page }) => {
    await page.goto("/admin/docs", { waitUntil: "domcontentloaded" });

    const runbookCard = page
      .getByTestId("docs-hub-card")
      .filter({ hasText: "Pre-deploy guard" });
    await expect(runbookCard).toBeVisible();

    await page.getByTestId("docs-hub-filter-philosophy").click();
    await expect(runbookCard).toHaveCount(0);

    await expect(
      page.getByTestId("docs-hub-card").filter({ hasText: "Brain Philosophy" }),
    ).toBeVisible();
  });
});
