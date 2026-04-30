import { test, expect } from "@playwright/test";

test.describe("Circles & delegated access (WS-76 PR-28 — STUDIO_E2E_FIXTURE=1)", () => {
  test("circles page shows seed household card and members", async ({ page }) => {
    await page.goto("/admin/circles", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("admin-circles-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("circle-card-circle-1")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Sharma Family" })).toBeVisible();
    const members = page.getByTestId("circle-members-circle-1");
    await expect(members.getByText("Sankalp")).toBeVisible();
    await expect(members.getByText("Olga")).toBeVisible();
  });

  test("delegated page lists active share; revoke hides row (UI only)", async ({ page }) => {
    await page.goto("/admin/delegated", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("admin-delegated-page")).toBeVisible({ timeout: 30_000 });
    const row = page.getByTestId("delegated-share-share-1");
    await expect(row).toBeVisible();
    await expect(row.getByText("Sam (CPA)")).toBeVisible();
    await expect(row.getByText("expenses:read")).toBeVisible();
    await page.getByTestId("revoke-share-share-1").click();
    await expect(page.getByTestId("delegated-share-share-1")).toHaveCount(0);
    await expect(page.getByText("No active delegated shares.")).toBeVisible();
  });
});
