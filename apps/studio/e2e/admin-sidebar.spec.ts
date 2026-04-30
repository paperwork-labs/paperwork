import { test, expect } from "@playwright/test";

test.describe("Admin sidebar (E2E — STUDIO_E2E_FIXTURE=1 dev server)", () => {
  test("WS-69 PR B: 15 nav links, Brain group, expenses link, 6 vendor footer links", async ({
    page,
  }) => {
    await page.goto("/admin", { waitUntil: "domcontentloaded" });
    const nav = page.getByRole("navigation", { name: "Admin" });
    await expect(nav.getByRole("link")).toHaveCount(15);
    await expect(nav.getByText("Brain", { exact: true })).toBeVisible();
    await expect(
      nav.getByRole("link", { name: /Expenses/i }),
    ).toHaveAttribute("href", "/admin/expenses");
    await expect(
      nav.getByRole("link", { name: /Founder actions/i }),
    ).toHaveCount(0);
    const footer = page.getByTestId("admin-vendor-footer");
    await expect(footer.getByRole("link")).toHaveCount(6);
    await expect(footer.getByText("Hosting")).toBeVisible();
    await expect(footer.getByText("AI cost")).toBeVisible();
  });
});
