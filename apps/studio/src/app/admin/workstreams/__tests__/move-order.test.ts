import { describe, expect, it } from "vitest";

import { moveOrderedIds } from "../move-order";

describe("moveOrderedIds", () => {
  it("reorders two adjacent ids", () => {
    const next = moveOrderedIds(["a", "b", "c"], "a", "b");
    expect(next).toEqual(["b", "a", "c"]);
  });

  it("returns null when ids unchanged", () => {
    expect(moveOrderedIds(["x", "y"], "x", "x")).toBeNull();
  });
});
