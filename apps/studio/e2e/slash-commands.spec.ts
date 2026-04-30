import { test, expect } from "@playwright/test";

test.describe("Conversations slash commands (WS-76 PR-22 — STUDIO_E2E_FIXTURE=1)", () => {
  test("typing / shows menu; selecting expense inserts /expense ", async ({ page }) => {
    await page.goto("/admin/brain/conversations", { waitUntil: "domcontentloaded" });
    const list = page.getByTestId("conversations-inbox-list");
    await expect(list).toBeVisible({ timeout: 30_000 });
    await list.getByRole("button").first().click();

    const textarea = page.getByTestId("conversation-reply-textarea");
    await textarea.fill("/");
    const menu = page.getByTestId("slash-command-menu");
    await expect(menu).toBeVisible();

    await page.locator('[data-command="expense"]').click();
    await expect(textarea).toHaveValue("/expense ");
  });
});
