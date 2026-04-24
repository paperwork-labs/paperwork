import { describe, expect, it, vi, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";

vi.mock("framer-motion", async () => {
  const actual = await vi.importActual<typeof import("framer-motion")>(
    "framer-motion",
  );
  return {
    ...actual,
    useReducedMotion: vi.fn(() => false),
  };
});

import {
  DURATION,
  EASE,
  INSTANT,
  chartReveal,
  fadeIn,
  scaleIn,
  slideDown,
  slideUp,
  staggerChildren,
  useMotionPreset,
} from "../motion";
import { useReducedMotion } from "framer-motion";

const useReducedMotionMock = vi.mocked(useReducedMotion);

afterEach(() => {
  useReducedMotionMock.mockReturnValue(false);
});

describe("EASE constants", () => {
  it("exposes the four named cubic-bezier curves with 4-tuple shape", () => {
    for (const name of ["standard", "emphasized", "spring", "glide"] as const) {
      const tuple = EASE[name];
      expect(Array.isArray(tuple)).toBe(true);
      expect(tuple).toHaveLength(4);
      tuple.forEach((n) => expect(typeof n).toBe("number"));
    }
  });
});

describe("DURATION constants", () => {
  it("are strictly increasing across the semantic ramp", () => {
    const ramp = [
      DURATION.instant,
      DURATION.fast,
      DURATION.base,
      DURATION.medium,
      DURATION.slow,
      DURATION.chartReveal,
    ];
    for (let i = 1; i < ramp.length; i++) {
      expect(ramp[i]).toBeGreaterThan(ramp[i - 1]);
    }
  });
});

describe("named variants", () => {
  it("each define the standard hidden/visible states", () => {
    for (const v of [fadeIn, slideUp, slideDown, scaleIn, chartReveal]) {
      expect(v).toHaveProperty("hidden");
      expect(v).toHaveProperty("visible");
    }
  });

  it("slideUp moves up from y=12 and fades in", () => {
    expect(slideUp.hidden).toMatchObject({ opacity: 0, y: 12 });
    expect(slideUp.visible).toMatchObject({ opacity: 1, y: 0 });
  });

  it("scaleIn uses the spring easing", () => {
    const visible = scaleIn.visible as { transition?: { ease?: unknown } };
    expect(visible.transition?.ease).toEqual(EASE.spring);
  });

  it("chartReveal uses clipPath and the glide easing", () => {
    expect(chartReveal.hidden).toMatchObject({
      clipPath: expect.stringContaining("inset"),
    });
    const visible = chartReveal.visible as { transition?: { ease?: unknown } };
    expect(visible.transition?.ease).toEqual(EASE.glide);
  });
});

describe("staggerChildren factory", () => {
  it("converts ms to seconds for staggerChildren", () => {
    const v = staggerChildren(80);
    const visible = v.visible as { transition?: { staggerChildren?: number } };
    expect(visible.transition?.staggerChildren).toBeCloseTo(0.08, 5);
  });

  it("defaults to 60 ms / 0.06 s", () => {
    const v = staggerChildren();
    const visible = v.visible as { transition?: { staggerChildren?: number } };
    expect(visible.transition?.staggerChildren).toBeCloseTo(0.06, 5);
  });
});

describe("useMotionPreset", () => {
  it("returns the named preset under normal motion", () => {
    useReducedMotionMock.mockReturnValue(false);
    const { result } = renderHook(() => useMotionPreset("slideUp"));
    expect(result.current).toBe(slideUp);
  });

  it("returns the INSTANT no-op variant when the user prefers reduced motion", () => {
    useReducedMotionMock.mockReturnValue(true);
    const { result } = renderHook(() => useMotionPreset("chartReveal"));
    expect(result.current).toBe(INSTANT);
  });
});
