/**
 * WS-76 PR-D — keyboard focus chrome + viewport geometry (Playwright).
 */

import { test, expect } from "@playwright/test";

test.describe.configure({ timeout: 90_000 });

test.describe("Admin a11y pass (keyboard + viewport)", () => {
  async function tabUntilFocusedDataTestId(
    page: import("@playwright/test").Page,
    testId: string,
    maxSteps = 60,
  ): Promise<void> {
    for (let i = 0; i < maxSteps; i++) {
      const cur = await page.evaluate(() =>
        document.activeElement?.getAttribute("data-testid"),
      );
      if (cur === testId) return;
      await page.keyboard.press("Tab");
    }
    throw new Error(`Tab ramp did not focus data-testid=${testId}`);
  }

  test("command palette opener and sidebar home show keyboard focus chrome", async ({ page }) => {
    test.setTimeout(120_000);

    await page.goto("/admin", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("admin-shell")).toBeVisible({ timeout: 30_000 });

    await tabUntilFocusedDataTestId(page, "admin-header-command-palette", 55);
    const paletteBtn = page.getByTestId("admin-header-command-palette");
    await expect(paletteBtn).toBeFocused();
    const pbShadow = await paletteBtn.evaluate((el: HTMLElement) => getComputedStyle(el).boxShadow);
    expect(pbShadow).not.toBe("none");

    await tabUntilFocusedDataTestId(page, "admin-sidebar-home-link", 80);
    const homeFocused = page.locator("[data-testid='admin-sidebar-home-link']:focus");
    await expect(homeFocused).toHaveCount(1);
    const homeShadow = await homeFocused.evaluate((el: HTMLElement) => getComputedStyle(el).boxShadow);
    expect(homeShadow).not.toBe("none");
    await expect(homeFocused).toHaveAttribute("href", "/admin");
  });

  test("375px: no horizontal scroll on admin overview", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/admin", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("admin-shell")).toBeVisible({ timeout: 30_000 });

    const overflowPx = await page
      .getByTestId("admin-shell")
      .evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(overflowPx, "no horizontal overflow at 375").toBeLessThanOrEqual(8);
  });

  test("375px: admin segment 404 stays within shell width", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/admin/ws76-playwright-unknown-route-a11y", {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("admin-shell")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("hq-empty-state")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("link", { name: /^Back to admin$/ })).toBeVisible();

    const overflowPx = await page
      .getByTestId("admin-shell")
      .evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(overflowPx, "404 view: no horizontal overflow at 375").toBeLessThanOrEqual(8);
  });

  test("command palette filter input exposes focus-visible ring after open", async ({ page }) => {
    await page.goto("/admin", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("admin-shell")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("admin-header-command-palette").click();
    const input = page.locator("[cmdk-input]").first();
    await expect(input).toBeVisible();
    await input.evaluate((el: HTMLElement) => {
      try {
        el.focus({ focusVisible: true } as FocusOptions & { focusVisible?: boolean });
      } catch {
        el.focus();
      }
    });
    await expect(input).toBeFocused();
    const boxShadow = await input.evaluate((el: HTMLElement) => getComputedStyle(el).boxShadow);
    expect(boxShadow, "palette search focus chrome").not.toBe("none");
    await page.keyboard.press("Escape");
  });

  test("architecture tabs show focus chrome on Analytics tab trigger", async ({ page }) => {
    const resp = await page.goto("/admin/architecture?tab=overview", {
      waitUntil: "domcontentloaded",
    });
    if (!resp || resp.status() === 404) {
      test.skip();
      return;
    }
    await expect(page.getByTestId("admin-shell")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("studio-page-tabs")).toBeVisible({ timeout: 25_000 });

    const analytics = page.getByRole("tab", { name: "Analytics" });
    await analytics.evaluate((el: HTMLElement) => {
      try {
        el.focus({ focusVisible: true } as FocusOptions & { focusVisible?: boolean });
      } catch {
        el.focus();
      }
    });

    await expect(analytics).toBeFocused({ timeout: 8000 });

    const boxShadow = await analytics.evaluate((el: HTMLElement) => getComputedStyle(el).boxShadow);
    const outlineWidth = await analytics.evaluate((el: HTMLElement) =>
      getComputedStyle(el).outlineWidth,
    );

    expect(boxShadow !== "none" || outlineWidth !== "0px").toBeTruthy();
  });
});
