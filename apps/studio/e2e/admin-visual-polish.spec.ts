/**
 * Visual regression — five most-visited admin routes (WS-76 Wave L PR-C).
 * Baselines: `pnpm --filter studio run test:e2e:visual -- --update-snapshots`
 */

import { test, expect } from "@playwright/test";

const ROUTES = [
  "/admin",
  "/admin/workstreams",
  "/admin/sprints",
  "/admin/infrastructure",
  "/admin/brain/conversations",
] as const;

test.describe("Admin visual baseline (WS-76 PR-C)", () => {
  test.describe.configure({ timeout: 120_000 });

  for (const path of ROUTES) {
    test(`snapshot ${path}`, async ({ page }) => {
      await page.goto(path, { waitUntil: "domcontentloaded", timeout: 90_000 });
      await expect(page.getByRole("main")).toBeVisible({ timeout: 60_000 });
      await expect(page).toHaveScreenshot({
        fullPage: true,
        maxDiffPixelRatio: 0.06,
      });
    });
  }
});
