import { test, expect } from "@playwright/test";

test.describe("Command palette (E2E — STUDIO_E2E_FIXTURE=1)", () => {
  test("WS-76 PR-15: Cmd/Ctrl+K opens palette; search filters items", async ({ page }) => {
    await page.goto("/admin", { waitUntil: "domcontentloaded" });
    await page.locator("main").click();

    // Chromium often binds Control+K to the address bar; Meta+K reaches the app on macOS.
    await page.keyboard.press("Meta+KeyK");
    const dialog = page.getByRole("dialog", { name: "Command palette" });
    await expect(dialog).toBeVisible();

    const input = page.getByPlaceholder("Search Studio...");
    await expect(input).toBeFocused();

    await input.fill("workstream");
    await expect(dialog.getByText("Workstreams", { exact: true })).toBeVisible();
    await expect(dialog.getByText("Overview", { exact: true })).toHaveCount(0);
  });
});
