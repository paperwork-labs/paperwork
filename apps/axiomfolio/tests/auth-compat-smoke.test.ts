import { describe, expect, it } from "vitest";

import { safeAppReturnPath } from "../src/lib/safe-app-return-path";

describe("WS-14 auth compat smoke", () => {
  it("safeAppReturnPath rejects open redirects and auth entry routes", () => {
    expect(safeAppReturnPath("//evil.com")).toBeNull();
    expect(safeAppReturnPath("https://x.com")).toBeNull();
    expect(safeAppReturnPath("/sign-in")).toBeNull();
    expect(safeAppReturnPath("/portfolio")).toBe("/portfolio");
  });

  it("useAuthCompat can be imported (hook is a function)", async () => {
    const { useAuthCompat } = await import("../src/lib/auth-compat");
    expect(useAuthCompat).toBeTypeOf("function");
  });
});
