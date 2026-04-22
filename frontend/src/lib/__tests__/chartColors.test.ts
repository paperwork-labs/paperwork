import { describe, expect, it } from "vitest";

import { canvasSafeColor, cssVarToCanvasColor } from "../chartColors";

describe("canvasSafeColor", () => {
  it("passes hex through unchanged", () => {
    expect(canvasSafeColor("#2563EB", "#000")).toBe("#2563EB");
    expect(canvasSafeColor("#fff", "#000")).toBe("#fff");
  });

  it("passes rgb/rgba/hsl through unchanged", () => {
    expect(canvasSafeColor("rgb(37, 99, 235)", "#000")).toBe("rgb(37, 99, 235)");
    expect(canvasSafeColor("rgba(0,0,0,0.5)", "#000")).toBe("rgba(0,0,0,0.5)");
    expect(canvasSafeColor("hsl(220 100% 50%)", "#000")).toBe(
      "hsl(220 100% 50%)",
    );
  });

  it("returns fallback for empty or whitespace input", () => {
    expect(canvasSafeColor("", "#abcdef")).toBe("#abcdef");
    expect(canvasSafeColor("   ", "#abcdef")).toBe("#abcdef");
  });

  it("rejects invalid-length hex (e.g. 5 digits) in favor of fallback", () => {
    expect(canvasSafeColor("#12345", "rgb(9,9,9)")).toBe("rgb(9,9,9)");
  });

  it("routes oklch / color-mix through the DOM probe", () => {
    // jsdom does not resolve oklch to rgb; the probe yields an empty /
    // unchanged `color` style, which causes the helper to fall back — and
    // that's exactly what we want, because the fallback is ALWAYS canvas-safe.
    const result = canvasSafeColor(
      "oklch(0.141 0.005 285.823)",
      "rgb(15, 23, 42)",
    );
    expect(result).toMatch(/^rgba?\(/);
  });
});

describe("cssVarToCanvasColor", () => {
  it("wraps space-separated RGB triples into rgb()", () => {
    document.documentElement.style.setProperty("--test-rgb", "37 99 235");
    expect(cssVarToCanvasColor("--test-rgb", "#000")).toBe("rgb(37, 99, 235)");
    document.documentElement.style.removeProperty("--test-rgb");
  });

  it("wraps RGB/alpha triples into legacy-comma rgba()", () => {
    document.documentElement.style.setProperty("--test-rgba", "0 0 0 / 0.5");
    expect(cssVarToCanvasColor("--test-rgba", "#000")).toBe(
      "rgba(0, 0, 0, 0.5)",
    );
    document.documentElement.style.removeProperty("--test-rgba");
  });

  it("falls back when the variable is unset", () => {
    expect(cssVarToCanvasColor("--does-not-exist", "#abcdef")).toBe("#abcdef");
  });
});
