import { expect, test } from "@playwright/test";

test.describe("Conversations spaces (WS-76 PR-21 — STUDIO_E2E_FIXTURE=1)", () => {
  test("space filter narrows inbox vs All", async ({ page }) => {
    await page.goto("/admin/conversations", { waitUntil: "domcontentloaded" });
    const list = page.getByTestId("conversations-inbox-list");
    await expect(list).toBeVisible({ timeout: 30_000 });
    const countAll = await list.getByRole("listitem").count();
    expect(countAll).toBeGreaterThan(1);

    await page.getByTestId("conversation-space-filter-personal").click();
    await expect(list).toBeVisible();
    const countPersonal = await list.getByRole("listitem").count();
    expect(countPersonal).toBeGreaterThan(0);
    expect(countPersonal).toBeLessThan(countAll);

    await page.getByTestId("conversation-space-filter-all").click();
    await expect(list.getByRole("listitem")).toHaveCount(countAll);
  });

  test("compose infers AxiomFolio space from title and shows chip after create", async ({ page }) => {
    await page.goto("/admin/conversations", { waitUntil: "domcontentloaded" });

    await page.getByRole("button", { name: "Compose" }).click();
    await expect(page.getByTestId("compose-modal")).toBeVisible({ timeout: 15_000 });

    await page.getByTestId("compose-title-input").fill("AxiomFolio rollout checkpoint");
    await expect(page.getByTestId("compose-space-select")).toHaveValue("axiomfolio");

    const submit = page.getByTestId("compose-submit");
    await submit.scrollIntoViewIfNeeded();
    await submit.click();
    await expect(page.getByTestId("compose-modal")).toBeHidden({ timeout: 15_000 });
    await expect(page.getByTestId("conversation-detail-space")).toContainText("AxiomFolio");
  });
});
