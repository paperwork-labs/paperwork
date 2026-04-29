import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "happy-dom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "src/**/__tests__/**/*.test.tsx"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      include: [
        "src/components/tabbed-page-shell.tsx",
        "src/components/settings-shell.tsx",
        "src/components/filter-chip-row.tsx",
        "src/components/cursor-paginated-list.tsx",
        "src/components/drop-zone.tsx",
        "src/components/status-badge.tsx",
      ],
      thresholds: {
        lines: 80,
        statements: 80,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
