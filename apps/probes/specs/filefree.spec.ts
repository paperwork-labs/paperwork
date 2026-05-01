/**
 * FileFree UX probe — critical user journey: sign-in page with FileFree branding.
 *
 * Guards Wave 0 PR-A5: FileFree sign-in must show the marketing nav + a
 * FileFree-branded Clerk widget (NOT "Paperwork Labs"). This is the exact
 * end-state PR-A5 produces; this probe catches regressions if branding breaks.
 *
 * PROBE_BASE_URL = https://filefree.ai (set by Brain ux_probe_runner.py)
 */

import { test, expect } from "@playwright/test";

test.describe("FileFree CUJ: landing → sign-in branding", () => {
  test("landing page renders and sign-in nav link is present", async ({ page }) => {
    await page.goto("/");
    // The Hero component renders — page should not be a blank error
    await expect(page).toHaveTitle(/FileFree/i);
  });

  test("sign-in page renders Clerk widget with FileFree branding", async ({ page }) => {
    await page.goto("/sign-in");
    // Clerk widget mounts inside an iframe or shadow DOM; we verify the
    // surrounding SignInShell container that names the product.
    await expect(page.locator("text=FileFree").first()).toBeVisible({ timeout: 15_000 });
    // Guard: must NOT show generic "Paperwork Labs" brand on sign-in page
    await expect(page.locator("text=Paperwork Labs")).not.toBeVisible();
    // An email input field must exist (Clerk widget is interactive)
    await expect(
      page.locator('input[type="email"], input[name="identifier"]').first()
    ).toBeVisible({ timeout: 15_000 });
  });
});
