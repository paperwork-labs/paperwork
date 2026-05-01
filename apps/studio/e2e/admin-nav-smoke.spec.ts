/**
 * Track C — Smoke every sidebar nav target from `src/lib/admin-navigation.tsx`.
 *
 * Run via Playwright webServer (`pnpm run dev:e2e` → STUDIO_E2E_FIXTURE=1). `/admin`
 * is ungated in NODE_ENV=development (see middleware).
 *
 * Money routes (/admin/expenses, /admin/bills) render full HQ headers only when
 * BRAIN_API_URL + BRAIN_API_SECRET resolve; otherwise they intentionally show Brain
 * configuration panels (red bordered) and this suite will flag them until Brain is wired.
 */

import { test, expect, type ConsoleMessage, type Page } from "@playwright/test";

type NavSmokeItem = {
  href: string;
  navLabel: string;
  /** <h1> in main — string or regexp (HqPageHeader always uses an h1 for titled pages). */
  heading: string | RegExp;
};

/** Every `href` from `buildNavGroups` in `admin-navigation.tsx` (order preserved). */
const navItems = [
  { href: "/admin", navLabel: "Overview", heading: "Company HQ" },
  { href: "/admin/conversations", navLabel: "Conversations", heading: "Conversations" },
  { href: "/admin/autopilot", navLabel: "Autopilot", heading: "Autopilot" },
  { href: "/admin/people", navLabel: "People", heading: "People" },
  { href: "/admin/brain/self-improvement", navLabel: "Self-improvement", heading: /Self-improvement/ },
  { href: "/admin/workstreams", navLabel: "Workstreams", heading: "Workstreams" },
  { href: "/admin/products", navLabel: "Products", heading: "Products" },
  { href: "/admin/goals", navLabel: "Goals", heading: /Goals & OKRs/ },
  { href: "/admin/architecture", navLabel: "Architecture", heading: "Architecture" },
  { href: "/admin/infrastructure", navLabel: "Infrastructure", heading: "Infrastructure" },
  {
    href: "/admin/docs/day-0-founder-actions",
    navLabel: "Day-0 checklist",
    heading: /Day-0 Founder Actions Worksheet/,
  },
  { href: "/admin/docs", navLabel: "Docs", heading: "Docs" },
  { href: "/admin/expenses", navLabel: "Expenses", heading: "Expenses" },
  { href: "/admin/vendors", navLabel: "Vendors", heading: "Vendors" },
  { href: "/admin/bills", navLabel: "Bills", heading: "Bills" },
] satisfies NavSmokeItem[];

const FORBIDDEN_TEXT_RE =
  /\b(?:HTTP\s+\d{3}|could\s+not\s+finish\s+setup|Brain.*unavailable|Live\s+data\s+unavailable)\b/i;

/**
 * Promo / alert panels Studio uses for hard failures — avoids incidental `bg-red-*`
 * badges (e.g. Autopilot KPI tones) which are normal UI chrome.
 */
const ERROR_BANNER_SELECTOR =
  '[class*="rounded"][class*="border-red"][class*="bg-red"],' +
  '[class*="rounded"][class*="border-rose"][class*="bg-rose"],' +
  '[class*="bg-red-500/5"],' +
  '[class*="bg-rose-500/5"]';

function recordConsoleSmoke(msg: ConsoleMessage, bucket: { errors: string[] }) {
  if (msg.type() !== "error") return;
  const text = msg.text();

  /* Known third-party chatter only — keep this list minimal. */
  if (text.includes("ERR_BLOCKED_BY_CLIENT")) return;

  bucket.errors.push(text);
}

async function assertNoErrorSurface(page: Page) {
  const main = page.getByRole("main");
  await expect(main).toBeVisible({ timeout: 30_000 });

  const bodyVisible = await main.innerText();
  expect(bodyVisible, "fatal copy in page body").not.toMatch(FORBIDDEN_TEXT_RE);

  /* Visible alert-style panels — hidden tab panels are ignored. */
  await expect(main.locator(ERROR_BANNER_SELECTOR).filter({ visible: true })).toHaveCount(0);

  /* Fallback slabs (Brain misconfig / Brain fetch errors on Money routes). */
  await expect(
    main
      .locator('[class*="rounded"][class*="border-red"],[class*="rounded"][class*="border-rose"]')
      .filter({ visible: true })
      .filter({ hasText: /\bbrain api\b|could not load|temporarily unavailable|not configured\b/i }),
  ).toHaveCount(0);
}

test.describe.configure({ timeout: 90_000 });

test.describe("Admin nav smoke — every sidebar href (dev:e2e + STUDIO_E2E_FIXTURE=1)", () => {
  for (const item of navItems) {
    test(`${item.navLabel}: ${item.href}`, async ({ page }) => {
      const consoleBucket: { errors: string[] } = { errors: [] };
      const pageErrors: string[] = [];

      page.on("console", (msg) => recordConsoleSmoke(msg, consoleBucket));
      page.on("pageerror", (err) => pageErrors.push(err.message));

      const resp = await page.goto(item.href, { waitUntil: "domcontentloaded" });
      expect(resp?.status(), "unexpected HTTP failure at navigation").toBeLessThan(500);

      await page.waitForLoadState("networkidle", { timeout: 25_000 });

      await assertNoErrorSurface(page);

      const heading = typeof item.heading === "string" ? new RegExp(`^${item.heading}$`, "i") : item.heading;
      await expect(page.getByRole("main").getByRole("heading", { level: 1, name: heading })).toBeVisible({
        timeout: 25_000,
      });

      expect(pageErrors, "page errors").toEqual([]);
      expect(consoleBucket.errors, "console errors").toEqual([]);
    });
  }
});
