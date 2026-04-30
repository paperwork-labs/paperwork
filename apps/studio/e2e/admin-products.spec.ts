/**
 * Admin Products registry (WS-76 PR-23).
 *
 * Run against the dev server with STUDIO_E2E_FIXTURE=1:
 *   pnpm --filter studio run dev:e2e
 *   pnpm --filter studio exec playwright test e2e/admin-products.spec.ts
 */

import { test, expect } from "@playwright/test";

test.describe("Admin Products (WS-76 PR-23)", () => {
  test("registry grid shows seven products and opens AxiomFolio cockpit", async ({ page }) => {
    await page.goto("/admin/products", { waitUntil: "domcontentloaded" });
    const cards = page.getByTestId("product-registry-card");
    await expect(cards).toHaveCount(7, { timeout: 15_000 });

    await page
      .locator('[data-product-slug="axiomfolio"]')
      .getByRole("link", { name: "Open cockpit →" })
      .click();
    await expect(page).toHaveURL(/\/admin\/products\/axiomfolio\/?$/);

    await expect(
      page.getByRole("main").getByRole("heading", { level: 1, name: "AxiomFolio" }),
    ).toBeVisible({ timeout: 15_000 });
  });
});
