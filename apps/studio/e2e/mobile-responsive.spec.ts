import { test, expect, devices, type Page } from "@playwright/test";

const iphone12 = devices["iPhone 12"];

/** iPhone 12 layout metrics in Chromium (avoid WebKit-only device preset in Chromium CI). */
test.use({
  viewport: iphone12.viewport,
  userAgent: iphone12.userAgent,
  deviceScaleFactor: iphone12.deviceScaleFactor,
  isMobile: iphone12.isMobile,
  hasTouch: iphone12.hasTouch,
});

/**
 * WS-76 PR-14: mobile layouts + viewport sanity (STUDIO_E2E_FIXTURE=1 — see playwright.config webServer).
 */
test.describe("Admin mobile responsive (iPhone 12 viewport)", () => {
  async function assertNoHorizontalOverflowScoped(page: Page) {
    const overflowPx = await page.getByTestId("admin-shell").evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(overflowPx, "admin shell should not exceed its width").toBeLessThanOrEqual(8);
  }

  async function drawerRightEdgePx(page: Page): Promise<number> {
    const drawer = page.getByTestId("admin-mobile-drawer");
    await expect(drawer).toHaveCount(1, { timeout: 30_000 });
    return drawer.evaluate((el) => el.getBoundingClientRect().right);
  }

  test("mobile nav: sidebar off-canvas until hamburger opens drawer", async ({ page }) => {
    await page.goto("/admin", { waitUntil: "networkidle" }).catch(() => {});
    await page.goto("/admin", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("admin-shell")).toBeVisible({ timeout: 30_000 });

    expect(await drawerRightEdgePx(page)).toBeLessThanOrEqual(24);

    await expect(page.getByTestId("admin-mobile-menu-button")).toBeVisible();
    await page.getByTestId("admin-mobile-menu-button").click();

    await expect(page.getByTestId("admin-mobile-drawer").getByRole("navigation", { name: "Admin" })).toBeVisible();
    expect(await drawerRightEdgePx(page)).toBeGreaterThan(80);

    await page.keyboard.press("Escape");
    await page.waitForTimeout(250);
    expect(await drawerRightEdgePx(page)).toBeLessThanOrEqual(24);
  });

  test("key admin routes: scoped shell avoids horizontal overflow", async ({ page }) => {
    for (const path of ["/admin", "/admin/workstreams", "/admin/pr-pipeline"]) {
      await page.goto(path, { waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("admin-shell")).toBeVisible({ timeout: 30_000 });
      await assertNoHorizontalOverflowScoped(page);
    }
  });

  test("conversations shows inbox list without thread pane initially", async ({ page }) => {
    await page.goto("/admin/conversations", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("admin-shell")).toBeVisible({ timeout: 30_000 });
    await assertNoHorizontalOverflowScoped(page);

    await expect(page.getByTestId("conversations-inbox-list")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("conversations-thread-pane")).toBeHidden();

    await page.getByTestId("conversations-inbox-list").getByRole("button").first().click();
    await expect(page.getByPlaceholder("Reply… (markdown supported)")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("conversations-mobile-back")).toBeVisible();
    await expect(page.getByTestId("conversations-thread-pane")).toBeVisible();
    await page.getByTestId("conversations-mobile-back").click();
    await expect(page.getByTestId("conversations-inbox-list")).toBeVisible();
    await expect(page.getByTestId("conversations-thread-pane")).toBeHidden();
  });
});
