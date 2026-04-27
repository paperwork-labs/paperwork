import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:3004" },
  webServer: {
    command: "pnpm run dev:e2e",
    url: "http://127.0.0.1:3004",
    reuseExistingServer: !process.env.CI,
  },
});
