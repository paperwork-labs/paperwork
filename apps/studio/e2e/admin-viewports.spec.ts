/**
 * WS-76 PR-D — fixed admin shell widths at common breakpoints.
 */

import { test, expect } from "@playwright/test";

const VIEWPORTS = [
  { name: "375", width: 375, height: 812 },
  { name: "768", width: 768, height: 900 },
  { name: "1024", width: 1024, height: 800 },
  { name: "1440", width: 1440, height: 900 },
];

test.describe.configure({ timeout: 60_000 });

for (const vp of VIEWPORTS) {
  test.describe(`viewport ${vp.name}px`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    test(`/admin renders shell without horizontal overflow`, async ({ page }) => {
      await page.goto("/admin", { waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("admin-shell")).toBeVisible({ timeout: 30_000 });

      const overflowPx = await page
        .getByTestId("admin-shell")
        .evaluate((el) => el.scrollWidth - el.clientWidth);
      expect(overflowPx, "admin shell horizontal overflow").toBeLessThanOrEqual(8);

      await expect(page.getByTestId("admin-mobile-drawer").first()).toBeAttached();

      const main = page.locator("main").first();
      await expect(main).toBeVisible();
      const mw = await main.evaluate((el) => el.getBoundingClientRect().width);
      expect(mw, "main should have usable width").toBeGreaterThan(120);

      if (vp.width >= 768) {
        await expect(page.getByTestId("admin-sidebar-nav").nth(1)).toBeVisible({ timeout: 15_000 });
      } else {
        await expect(page.getByTestId("admin-sidebar-nav")).toHaveCount(2);
      }
    });
  });
}
