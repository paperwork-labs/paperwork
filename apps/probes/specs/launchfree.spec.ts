/**
 * LaunchFree UX probe — critical user journey: landing page has visible CTA
 * that navigates to the sign-up / onboarding flow.
 *
 * Guards Wave 0: LaunchFree home must render the primary "Start Your LLC" CTA
 * and clicking it must navigate to /form (onboarding step 1). Catches
 * blank-page or broken-link regressions in the entry funnel.
 *
 * PROBE_BASE_URL = https://launchfree.ai (set by Brain ux_probe_runner.py)
 */

import { test, expect } from "@playwright/test";

test.describe("LaunchFree CUJ: landing → start LLC flow", () => {
  test("landing page renders primary CTA", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/LaunchFree/i);
    const cta = page.locator("a, button").filter({ hasText: /Start Your LLC/i }).first();
    await expect(cta).toBeVisible({ timeout: 10_000 });
  });

  test("CTA click navigates to onboarding flow", async ({ page }) => {
    await page.goto("/");
    const cta = page.locator("a, button").filter({ hasText: /Start Your LLC/i }).first();
    await cta.click();
    // Must navigate away from landing — URL changes to /form or /sign-up
    await expect(page).not.toHaveURL("/", { timeout: 10_000 });
  });
});
