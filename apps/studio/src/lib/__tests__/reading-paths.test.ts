import { describe, expect, it } from "vitest";

import { validateReadingPaths } from "@/lib/reading-paths";

describe("reading-paths", () => {
  it("validateReadingPaths reports full resolution for every configured path", () => {
    const rows = validateReadingPaths();
    expect(rows.length).toBeGreaterThan(0);

    const broken = rows.filter((r) => r.unresolvedDocIds.length > 0);
    expect(broken).toEqual([]);

    for (const row of rows) {
      expect(row.resolvedSlugs.length).toBe(row.requestedDocIds.length);
    }
  });
});
