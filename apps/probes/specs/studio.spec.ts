/**
 * Studio UX probe — critical user journey: /admin loads without JS errors.
 *
 * Guards Wave 0: Studio /admin must render the command-center layout (or
 * redirect to /admin/sign-in) without crashing. Catches blank-page and
 * runtime-error regressions in the primary operator surface.
 *
 * PROBE_BASE_URL = https://studio.paperworklabs.com (set by Brain ux_probe_runner.py)
 */

import { test, expect } from "@playwright/test";

test.describe("Studio CUJ: /admin loads or redirects cleanly", () => {
  test("/admin renders or redirects to sign-in without crash", async ({ page }) => {
    const jsErrors: string[] = [];
    page.on("pageerror", (err) => jsErrors.push(err.message));

    const response = await page.goto("/admin");
    // Accept 200 (authed session) or redirect to sign-in (unauthenticated)
    const finalUrl = page.url();
    const isAdminOrLogin =
      finalUrl.includes("/admin") || finalUrl.includes("/sign-in") || finalUrl.includes("/login");

    expect(
      isAdminOrLogin,
      `Expected /admin to stay on /admin or redirect to sign-in, got: ${finalUrl}`
    ).toBe(true);

    // Page must not 500
    expect(response?.status() ?? 200, "HTTP error on /admin").toBeLessThan(500);

    // No fatal JS errors
    const fatalErrors = jsErrors.filter(
      (e) => !e.includes("ChunkLoadError") // filter transient Webpack chunk errors
    );
    expect(
      fatalErrors,
      `Fatal JS errors on Studio /admin: ${fatalErrors.join("; ")}`
    ).toHaveLength(0);
  });
});
