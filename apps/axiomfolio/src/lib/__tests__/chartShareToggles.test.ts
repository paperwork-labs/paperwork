import { describe, it, expect } from "vitest";

import { indicatorTogglesFromShareList } from "../chartShareToggles";

describe("indicatorTogglesFromShareList", () => {
  it("returns all-on defaults when list is empty", () => {
    const t = indicatorTogglesFromShareList(undefined);
    expect(t.trendLines && t.gaps && t.emas && t.stage).toBe(true);
  });

  it("enables only listed keys when a list is provided", () => {
    const t = indicatorTogglesFromShareList(["emas", "stage"]);
    expect(t.emas).toBe(true);
    expect(t.stage).toBe(true);
    expect(t.trendLines).toBe(false);
  });
});
