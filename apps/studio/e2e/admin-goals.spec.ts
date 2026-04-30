/**
 * Goals & OKRs page (WS-76 PR-16).
 *
 * Run against the dev server with STUDIO_E2E_FIXTURE=1:
 *   pnpm --filter studio run dev:e2e
 *   pnpm --filter studio exec playwright test e2e/admin-goals.spec.ts
 */

import { test, expect } from "@playwright/test";

test.describe("Admin Goals & OKRs (WS-76 PR-16)", () => {
  test("renders header title and subtitle", async ({ page }) => {
    await page.goto("/admin/goals", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("main").getByRole("heading", { name: "Goals & OKRs" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByText("Q2 2026 objectives and key results"),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("shows at least one objective card", async ({ page }) => {
    await page.goto("/admin/goals", { waitUntil: "domcontentloaded" });
    const cards = page.getByTestId("okr-objective-card");
    await expect(cards.first()).toBeVisible({ timeout: 15_000 });
    expect(await cards.count()).toBeGreaterThanOrEqual(1);
  });

  test("renders progress bars", async ({ page }) => {
    await page.goto("/admin/goals", { waitUntil: "domcontentloaded" });
    const bars = page.getByTestId("okr-progress-bar");
    await expect(bars.first()).toBeVisible({ timeout: 15_000 });
    expect(await bars.count()).toBeGreaterThanOrEqual(1);
  });
});
