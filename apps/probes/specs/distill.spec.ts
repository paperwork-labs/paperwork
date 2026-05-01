/**
 * Distill UX probe — critical user journey: landing page hero renders.
 *
 * Guards Wave 0: Distill home must render the main hero copy without JS errors.
 * Real CUJ (document ingestion flow) is deferred to PR-PB3 once Distill's
 * onboarding flow is production-ready.
 *
 * PROBE_BASE_URL = https://distill.ai (set by Brain ux_probe_runner.py)
 */

import { test, expect } from "@playwright/test";

test.describe("Distill CUJ: landing hero renders", () => {
  test("landing page loads with Distill hero copy", async ({ page }) => {
    const jsErrors: string[] = [];
    page.on("pageerror", (err) => jsErrors.push(err.message));

    await page.goto("/");
    await expect(page).toHaveTitle(/Distill/i);

    // Hero headline must be visible (guards blank-page regressions)
    await expect(
      page.locator("h1").filter({ hasText: /compliance|automation|document/i }).first()
    ).toBeVisible({ timeout: 10_000 });

    // No JS console errors on load
    expect(jsErrors, `JS errors on Distill landing: ${jsErrors.join("; ")}`).toHaveLength(0);
  });

  test("dashboard link is present", async ({ page }) => {
    await page.goto("/");
    // Placeholder dashboard link (from current page.tsx)
    const dashboardLink = page.locator("a").filter({ hasText: /dashboard/i }).first();
    await expect(dashboardLink).toBeVisible({ timeout: 10_000 });
  });
});
