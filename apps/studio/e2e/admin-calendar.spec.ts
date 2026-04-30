/**
 * Admin Calendar (WS-76 PR-17a).
 *
 * Run against the dev server with STUDIO_E2E_FIXTURE=1:
 *   pnpm --filter studio run dev:e2e
 *   pnpm --filter studio exec playwright test e2e/admin-calendar.spec.ts
 */

import { test, expect } from "@playwright/test";

test.describe("Admin Calendar (WS-76 PR-17a)", () => {
  test("renders Calendar header and subtitle", async ({ page }) => {
    await page.goto("/admin/calendar", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("main").getByRole("heading", { name: "Calendar" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.getByText("Sprint deadlines, milestones, and scheduled tasks"),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("month grid shows seven weekday column headers", async ({ page }) => {
    await page.goto("/admin/calendar", { waitUntil: "domcontentloaded" });
    const headers = page.getByTestId("calendar-weekday-header");
    await expect(headers).toHaveCount(7);
    await expect(page.getByTestId("calendar-month-grid")).toBeVisible({ timeout: 15_000 });
  });

  test("today cell is highlighted", async ({ page }) => {
    await page.goto("/admin/calendar", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("calendar-day-today")).toBeVisible({ timeout: 15_000 });
  });

  test("prev / next month navigation updates month label", async ({ page }) => {
    await page.goto("/admin/calendar", { waitUntil: "domcontentloaded" });
    const heading = page.getByRole("main").locator("h2").first();
    await expect(heading).toBeVisible({ timeout: 15_000 });
    const before = await heading.textContent();
    await page.getByTestId("calendar-nav-next").click();
    await expect(heading).not.toHaveText(before ?? "", { timeout: 10_000 });
    await page.getByTestId("calendar-nav-prev").click();
    await expect(heading).toHaveText(before ?? "", { timeout: 10_000 });
  });

  test("Today button returns view to current month", async ({ page }) => {
    await page.goto("/admin/calendar", { waitUntil: "domcontentloaded" });
    const heading = page.getByRole("main").locator("h2").first();
    await expect(heading).toBeVisible({ timeout: 15_000 });
    const currentLabel = await heading.textContent();
    await page.getByTestId("calendar-nav-next").click();
    await expect(heading).not.toHaveText(currentLabel ?? "");
    await page.getByTestId("calendar-nav-today").click();
    await expect(heading).toHaveText(currentLabel ?? "", { timeout: 10_000 });
    await expect(page.getByTestId("calendar-day-today")).toBeVisible({ timeout: 10_000 });
  });
});
