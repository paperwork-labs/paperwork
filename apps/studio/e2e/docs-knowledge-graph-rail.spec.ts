/**
 * Docs knowledge rail (WS-76 PR-19): backlinks sidebar on doc detail pages.
 *
 * Run: pnpm --filter @paperwork-labs/studio exec playwright test e2e/docs-knowledge-graph-rail.spec.ts
 */

import { expect, test } from "@playwright/test";

test.describe("Doc knowledge rail (backlinks)", () => {
  test("Brain Architecture shows backlinks rail and seeded linker", async ({
    page,
  }) => {
    await page.goto("/admin/docs/brain-architecture", { waitUntil: "domcontentloaded" });

    const panel = page.getByTestId("doc-backlinks-panel").first();
    await expect(panel).toBeVisible();

    await expect(panel.getByTestId("doc-linked-from-count")).toContainText("backlink");

    await expect(panel.getByRole("link", { name: "Brain Personas (generated)" }).first()).toBeVisible();

    await expect(panel.getByTestId("doc-related-workstreams")).toContainText("WS-76");
  });
});
