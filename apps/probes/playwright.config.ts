import { defineConfig, devices } from "@playwright/test";
import path from "path";

/**
 * Wave PROBE — synthetic UX probe playwright config.
 *
 * PROBE_BASE_URL: per-product production URL, injected by ux_probe_runner.py.
 * Results are written to apps/probes/results/<product>-<timestamp>.json for
 * Brain scheduler consumption.
 */

const baseURL = process.env.PROBE_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./specs",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 1,
  timeout: 30_000,
  reporter: [
    ["list"],
    [
      "json",
      {
        outputFile: path.join(
          "results",
          `${process.env.PROBE_PRODUCT ?? "unknown"}-${Date.now()}.json`
        ),
      },
    ],
  ],
  use: {
    baseURL,
    trace: "on-first-retry",
    video: "on-first-retry",
    screenshot: "only-on-failure",
    headless: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
