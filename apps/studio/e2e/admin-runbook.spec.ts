/**
 * `/admin/runbook` redirects to the Day-0 founder actions doc in the Docs hub.
 *
 * Run against the dev server:
 *   pnpm --filter studio run dev:e2e   # in one terminal
 *   pnpm --filter studio exec playwright test e2e/admin-runbook.spec.ts
 */

import { test, expect } from "@playwright/test";

test.describe("Admin Runbook redirect → Day-0 doc", () => {
  test("runbook URL lands on day-0-founder-actions doc", async ({ page }) => {
    const resp = await page.goto("/admin/runbook", { waitUntil: "domcontentloaded" });
    expect(resp?.status()).toBeLessThan(500);
    await expect(page).toHaveURL(/\/admin\/docs\/day-0-founder-actions\b/);
    await expect(
      page.getByRole("main").getByRole("heading", { level: 1, name: /Day-0 Founder Actions Worksheet/ }),
    ).toBeVisible({ timeout: 15_000 });
  });
});
