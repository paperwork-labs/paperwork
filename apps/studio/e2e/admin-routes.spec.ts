import { test, expect } from "@playwright/test";

/**
 * Post–PR B/C IA: 13 sidebar entries + every PR C redirect source.
 * @see .cursor/plans/studio_ia_reorg_plan_2033873b.plan.md
 */
const PRIMARY_ADMIN_ROUTES = [
  "/admin",
  "/admin/tasks",
  "/admin/products",
  "/admin/sprints",
  "/admin/workstreams",
  "/admin/expenses",
  "/admin/pr-pipeline",
  "/admin/architecture",
  "/admin/docs",
  "/admin/infrastructure",
  "/admin/brain/personas",
  "/admin/brain/conversations",
  "/admin/brain/self-improvement",
] as const;

const PR_C_REDIRECT_SOURCES = [
  "/admin/founder-actions",
  "/admin/workflows",
  "/admin/agents",
  "/admin/ops",
  "/admin/n8n-mirror",
  "/admin/automation",
  "/admin/brain/learning",
  "/admin/brain-learning",
  "/admin/analytics",
  "/admin/secrets",
] as const;

const ALL_ROUTES = [...PRIMARY_ADMIN_ROUTES, ...PR_C_REDIRECT_SOURCES];

const REDIRECT_STATUS = [301, 302, 303, 307, 308];

async function assertHealthyChain(
  baseURL: string,
  request: import("@playwright/test").APIRequestContext,
  path: string,
): Promise<void> {
  const seen = new Set<string>();
  let url = new URL(path, baseURL).href;
  for (let i = 0; i < 24; i++) {
    const res = await request.get(url, { maxRedirects: 0 });
    const st = res.status();
    if (st >= 500) {
      throw new Error(`${path}: ${st} from ${url}`);
    }
    if (st >= 200 && st < 300) {
      return;
    }
    if (REDIRECT_STATUS.includes(st)) {
      const loc = res.headers()["location"];
      if (!loc) {
        throw new Error(`${path}: redirect ${st} missing Location (${url})`);
      }
      const next = new URL(loc, url).href;
      if (seen.has(next)) {
        throw new Error(`${path}: redirect loop involving ${next}`);
      }
      seen.add(next);
      url = next;
      continue;
    }
    throw new Error(`${path}: unexpected ${st} for ${url}`);
  }
  throw new Error(`${path}: too many redirects`);
}

test.describe("Admin route smoke (WS-69 PR A)", () => {
  test("13-item nav + PR C redirect sources resolve without 5xx or loops", async ({
    baseURL,
    request,
  }) => {
    expect(baseURL).toBeTruthy();
    for (const path of ALL_ROUTES) {
      await assertHealthyChain(baseURL!, request, path);
    }
  });

  test("/admin/workstreams renders the board", async ({ page }) => {
    await page.goto("/admin/workstreams", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: /^Workstreams$/i })).toBeVisible();
    await expect(page.getByTestId("workstreams-board")).toBeVisible();
  });
});
