import { describe, expect, it } from "vitest";

describe("clerk-api-token bridge", () => {
  it("exports setClerkApiTokenGetter and getClerkSessionTokenForApi", async () => {
    const mod = await import("../src/lib/clerk-api-token");
    expect(mod.setClerkApiTokenGetter).toBeTypeOf("function");
    expect(mod.getClerkSessionTokenForApi).toBeTypeOf("function");
  });
});
