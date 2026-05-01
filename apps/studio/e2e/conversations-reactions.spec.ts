import { test, expect } from "@playwright/test";

test.describe("Conversations reactions (WS-76 PR-20 — STUDIO_E2E_FIXTURE=1)", () => {
  test("hover message, pick thumbs-up — reaction pill shows count 1", async ({ page }) => {
    await page.goto("/admin/conversations", { waitUntil: "domcontentloaded" });
    const list = page.getByTestId("conversations-inbox-list");
    await expect(list).toBeVisible({ timeout: 30_000 });
    await list.getByRole("button").first().click();

    const firstMessage = page.locator('[data-testid^="conversation-message-"]').first();
    await expect(firstMessage).toBeVisible({ timeout: 15_000 });
    await firstMessage.hover();

    const pick = page.getByTestId("conversation-reaction-pick-👍");
    await expect(pick).toBeVisible();
    await pick.click();

    const pill = page.getByTestId("conversation-reaction-👍");
    await expect(pill).toBeVisible();
    await expect(pill).toContainText("👍");
    await expect(pill).toContainText("1");
  });
});
