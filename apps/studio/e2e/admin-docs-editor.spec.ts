/**
 * Doc markdown editor (WS-76 PR-18).
 *
 * Uses dev server via playwright.config (`pnpm run dev:e2e`).
 */

import { test, expect } from "@playwright/test";

test.describe("Admin docs editor", () => {
  test("edit page loads editor and accepts typing", async ({ page }) => {
    await page.goto("/admin/docs/day-0-founder-actions/edit", {
      waitUntil: "domcontentloaded",
    });

    await expect(page.getByTestId("admin-doc-editor-root")).toBeVisible({
      timeout: 25_000,
    });
    await expect(page.getByTestId("admin-markdown-editor")).toBeVisible({
      timeout: 25_000,
    });

    const editor = page.getByTestId("admin-markdown-editor-body").locator(".ProseMirror");
    await expect(editor.first()).toBeVisible({ timeout: 15_000 });
    await editor.first().click();
    await page.keyboard.type("E2E_WS76_PR18");
    await expect(editor.first()).toContainText("E2E_WS76_PR18", { timeout: 10_000 });
  });
});
