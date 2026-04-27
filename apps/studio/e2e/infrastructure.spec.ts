import { test, expect } from "@playwright/test";

test.describe("Admin infrastructure (E2E fixture — STUDIO_E2E_FIXTURE=1 dev server)", () => {
  test("at least 9 platform rows render with summary", async ({ page }) => {
    await page.goto("/admin/infrastructure", { waitUntil: "domcontentloaded" });
    const rows = page.getByTestId("infra-probe-row");
    await expect(rows).toHaveCount(9);
    await expect(page.getByTestId("infra-health-summary")).toBeVisible();
    await expect(page.getByTestId("infra-summary-render")).toContainText(/Render:/i);
    await expect(page.getByTestId("infra-summary-vercel")).toContainText(/Vercel:/i);
  });
});
