/**
 * WS-76 PR-D — keyboard focus chrome + viewport geometry (Playwright).
 */

import { test, expect } from "@playwright/test";

test.describe.configure({ timeout: 90_000 });

test.describe("Admin a11y pass (keyboard + viewport)", () => {
  async function expectKeyboardFocusChrome(locator: import("@playwright/test").Locator): Promise<void> {
    const boxShadow = await locator.evaluate((el: HTMLElement) => getComputedStyle(el).boxShadow);
    const outlineW = await locator.evaluate((el: HTMLElement) => getComputedStyle(el).outlineWidth);
    expect(
      (boxShadow && boxShadow !== "none") || outlineW !== "0px",
      "focus-visible ring (box-shadow) or outline",
    ).toBeTruthy();
  }

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

  async function shiftTabUntilFocusedDataTestId(
    page: import("@playwright/test").Page,
    testId: string,
    maxSteps = 60,
  ): Promise<void> {
    for (let i = 0; i < maxSteps; i++) {
      const cur = await page.evaluate(() =>
        document.activeElement?.getAttribute("data-testid"),
      );
      if (cur === testId) return;
      await page.keyboard.press("Shift+Tab");
    }
    throw new Error(`Shift+Tab ramp did not focus data-testid=${testId}`);
  }

  test("command palette opener and sidebar home show keyboard focus chrome", async ({ page }) => {
    test.setTimeout(120_000);

    await page.goto("/admin", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("admin-shell")).toBeVisible({ timeout: 30_000 });

    await tabUntilFocusedDataTestId(page, "admin-header-command-palette", 55);
    const paletteBtn = page.getByTestId("admin-header-command-palette");
    await expect(paletteBtn).toBeFocused();
    await expectKeyboardFocusChrome(paletteBtn);

    // Sidebar sits before the sticky header in DOM; forward Tab never returns to it — walk back.
    await shiftTabUntilFocusedDataTestId(page, "admin-sidebar-home-link", 40);
    const homeFocused = page.locator("[data-testid='admin-sidebar-home-link']:focus");
    await expect(homeFocused).toHaveCount(1);
    await expectKeyboardFocusChrome(homeFocused);
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
    await page.goto("/admin/ws76-a11y/playwright-unknown-route", {
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
    await expectKeyboardFocusChrome(input);
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
