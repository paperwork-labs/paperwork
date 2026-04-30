import { expect, test } from "@playwright/test";

test("sign-in page has marketing nav", async ({ page }) => {
  await page.goto("/sign-in");
  await expect(page.locator("nav")).toBeVisible();
  await expect(page.locator('nav a[href="/sign-up"]')).toBeVisible();
  await expect(page.locator('nav a[href="/pricing"]')).toBeVisible();
});

test("Clerk widget shows FileFree branding", async ({ page }) => {
  await page.goto("/sign-in");
  await page.waitForSelector("[data-clerk-id], .cl-card, .cl-rootBox", {
    timeout: 10000,
  });

  const body = await page.locator("body").textContent();
  expect(body).toContain("FileFree");
  expect(body).not.toContain("Paperwork Labs");
});
