import { describe, expect, it } from "vitest";

import { filterDispatchesToUtcToday } from "../dispatch-filters";

describe("filterDispatchesToUtcToday", () => {
  it("keeps only items created on the reference UTC day", () => {
    const ref = new Date("2026-05-01T15:00:00.000Z");
    const items = [
      { id: "a", created_at: "2026-05-01T08:00:00.000Z" },
      { id: "b", created_at: "2026-04-30T23:59:59.000Z" },
      { id: "c", created_at: "2026-05-02T00:00:00.000Z" },
    ];
    const out = filterDispatchesToUtcToday(items, ref);
    expect(out.map((i) => i.id)).toEqual(["a"]);
  });

  it("excludes items from previous UTC days", () => {
    const ref = new Date("2026-01-10T00:30:00.000Z");
    const items = [{ id: "old", created_at: "2026-01-09T12:00:00.000Z" }];
    expect(filterDispatchesToUtcToday(items, ref)).toHaveLength(0);
  });
});
