/**
 * AxiomFolio UX probe — critical user journey: sign-in page is interactive
 * with AxiomFolio branding and a working footer.
 *
 * Guards Wave 0: AxiomFolio sign-in must show the AxiomFolio-branded Clerk
 * widget (not "Paperwork Labs") and the sign-in form must be interactive
 * (email input exists). Footer must identify the product.
 *
 * PROBE_BASE_URL = https://axiomfolio.com (set by Brain ux_probe_runner.py)
 */

import { test, expect } from "@playwright/test";

test.describe("AxiomFolio CUJ: landing → sign-in interactive", () => {
  test("landing page renders AxiomFolio title", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/AxiomFolio/i);
  });

  test("sign-in page renders AxiomFolio-branded Clerk widget with interactive form", async ({
    page,
  }) => {
    await page.goto("/sign-in");
    // AxiomFolio branding must appear in the SignInShell
    await expect(page.locator("text=AxiomFolio").first()).toBeVisible({ timeout: 15_000 });
    // Guard: must NOT show "Paperwork Labs" brand
    await expect(page.locator("text=Paperwork Labs")).not.toBeVisible();
    // Email input exists (form is interactive)
    await expect(
      page.locator('input[type="email"], input[name="identifier"]').first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test("footer mentions AxiomFolio", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("footer").filter({ hasText: /AxiomFolio/i })).toBeVisible({
      timeout: 10_000,
    });
  });
});
