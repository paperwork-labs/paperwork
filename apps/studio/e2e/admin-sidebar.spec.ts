import { test, expect } from "@playwright/test";

test.describe("Admin sidebar (E2E — STUDIO_E2E_FIXTURE=1 dev server)", () => {
  test("WS-76 PR-26: Money + Trackers + Trust + Brain, Bills/Vendors/Cost monitor, 21 nav links, 6 vendor footer links", async ({
    page,
  }) => {
    await page.goto("/admin", { waitUntil: "domcontentloaded" });
    const nav = page.getByRole("navigation", { name: "Admin" }).first();
    await expect(nav.getByRole("link")).toHaveCount(21);
    await expect(nav.getByText("Money", { exact: true })).toBeVisible();
    await expect(nav.getByText("Trackers", { exact: true })).toBeVisible();
    await expect(nav.getByText("Brain", { exact: true })).toBeVisible();
    await expect(nav.getByText("Trust", { exact: true })).toBeVisible();
    await expect(nav.getByRole("link", { name: /^Circles$/ })).toHaveAttribute("href", "/admin/circles");
    await expect(nav.getByRole("link", { name: /Delegated access/i })).toHaveAttribute(
      "href",
      "/admin/delegated",
    );
    await expect(
      nav.getByRole("link", { name: /Expenses/i }),
    ).toHaveAttribute("href", "/admin/expenses");
    await expect(nav.getByRole("link", { name: /^Vendors$/ })).toHaveAttribute("href", "/admin/vendors");
    await expect(nav.getByRole("link", { name: /^Bills$/ })).toHaveAttribute("href", "/admin/bills");
    await expect(nav.getByRole("link", { name: /Cost monitor/i })).toHaveAttribute(
      "href",
      "/admin/infrastructure?tab=cost",
    );
    await expect(
      nav.getByRole("link", { name: /Founder actions/i }),
    ).toHaveCount(0);
    const footer = page.getByTestId("admin-vendor-footer").first();
    await expect(footer.getByRole("link")).toHaveCount(6);
    await expect(footer.getByText("Hosting")).toBeVisible();
    await expect(footer.getByText("AI cost")).toBeVisible();
  });
});
