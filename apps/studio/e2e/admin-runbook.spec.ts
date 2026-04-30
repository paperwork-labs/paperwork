/**
 * Smoke tests for the Day-0 founder runbook page (WS-76 PR-4).
 *
 * Run against the dev server:
 *   pnpm --filter studio run dev:e2e   # in one terminal
 *   pnpm --filter studio exec playwright test e2e/admin-runbook.spec.ts
 */

import { test, expect } from "@playwright/test";

test.describe("Admin Runbook page (WS-76 PR-4)", () => {
  test("renders page title 'Runbook'", async ({ page }) => {
    await page.goto("/admin/runbook", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("main").getByRole("heading", { name: "Runbook" }),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("renders subtitle text", async ({ page }) => {
    await page.goto("/admin/runbook", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByText("Day-0 setup checklist and operational tasks"),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("displays at least one checklist item", async ({ page }) => {
    await page.goto("/admin/runbook", { waitUntil: "domcontentloaded" });
    const items = page.getByTestId("runbook-item");
    await expect(items.first()).toBeVisible({ timeout: 15_000 });
    const count = await items.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test("displays stat cards", async ({ page }) => {
    await page.goto("/admin/runbook", { waitUntil: "domcontentloaded" });
    const cards = page.getByTestId("hq-stat-card");
    await expect(cards.first()).toBeVisible({ timeout: 15_000 });
    const count = await cards.count();
    expect(count).toBe(4);
  });

  test("/admin/founder-actions redirects to /admin/runbook", async ({ page }) => {
    const resp = await page.goto("/admin/founder-actions");
    expect(resp?.url()).toContain("/admin/runbook");
  });
});
