import { test, expect } from "@playwright/test";

test.describe("Conversations founder-actions backfill (WS-76 PR-2 — STUDIO_E2E_FIXTURE=1)", () => {
  test("inbox shows rows when founder-actions.json has tiers; badge matches inbox count", async ({
    page,
  }) => {
    await page.goto("/admin/brain/conversations", { waitUntil: "domcontentloaded" });
    const list = page.getByTestId("conversations-inbox-list");
    await expect(list).toBeVisible({ timeout: 30_000 });
    const rows = list.getByRole("button");
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(0);

    const badge = page.getByTestId("conversations-sidebar-badge");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText(new RegExp(`^${rowCount} pending$`));
  });

  test("navigate away and back — inbox still populated", async ({ page }) => {
    await page.goto("/admin/brain/conversations", { waitUntil: "domcontentloaded" });
    const list = page.getByTestId("conversations-inbox-list");
    await expect(list).toBeVisible({ timeout: 30_000 });
    const firstBefore = await list.getByRole("button").first().textContent();

    await page.goto("/admin/tasks", { waitUntil: "domcontentloaded" });
    await page.goto("/admin/brain/conversations", { waitUntil: "domcontentloaded" });
    await expect(list).toBeVisible({ timeout: 30_000 });
    const firstAfter = await list.getByRole("button").first().textContent();
    expect(firstAfter).toBe(firstBefore);
    const rowCount = await list.getByRole("button").count();
    expect(rowCount).toBeGreaterThan(0);
  });

  test("no duplicate rows by stable title after reload", async ({ page }) => {
    await page.goto("/admin/brain/conversations", { waitUntil: "domcontentloaded" });
    const list = page.getByTestId("conversations-inbox-list");
    await expect(list).toBeVisible({ timeout: 30_000 });
    const n = await list.getByRole("button").count();
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(list).toBeVisible({ timeout: 30_000 });
    const n2 = await list.getByRole("button").count();
    expect(n2).toBe(n);
  });
});
