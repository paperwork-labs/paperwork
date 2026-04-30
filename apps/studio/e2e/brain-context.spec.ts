import { test, expect } from "@playwright/test";

test.describe("Brain context picker (WS-76 PR-27 — STUDIO_E2E_FIXTURE=1)", () => {
  test("picker renders; switching updates badge; persists on reload", async ({
    page,
  }) => {
    await page.goto("/admin", { waitUntil: "domcontentloaded" });

    const shell = page.getByTestId("admin-shell");
    await expect(shell).toBeVisible({ timeout: 30_000 });

    const trigger = page.getByTestId("brain-context-picker-trigger");
    await expect(trigger).toBeVisible();

    const badge = page.getByTestId("brain-context-badge");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText("Paperwork Labs");

    await trigger.click();
    const household = page.getByTestId("brain-context-option-household");
    await expect(household).toBeVisible();
    await household.click();

    await expect(badge).toHaveText("Household");

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("admin-shell")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("brain-context-badge")).toHaveText("Household");
  });
});
