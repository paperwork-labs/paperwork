import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { MetricStripSkeleton } from "../MetricStripSkeleton";

describe("MetricStripSkeleton", () => {
  it("renders an aria-busy region with a screen-reader loading message", () => {
    render(<MetricStripSkeleton label="dashboard metrics" />);
    const node = screen.getByTestId("metric-strip-skeleton");
    expect(node).toHaveAttribute("aria-busy", "true");
    expect(node).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText(/loading dashboard metrics/i)).toBeInTheDocument();
  });

  it("defaults to 4 tiles, each with a label + value placeholder (8 skeletons total)", () => {
    render(<MetricStripSkeleton />);
    const node = screen.getByTestId("metric-strip-skeleton");
    expect(node.querySelectorAll('[data-slot="skeleton"]').length).toBe(8);
  });

  it("accepts a custom count prop", () => {
    render(<MetricStripSkeleton count={6} />);
    const node = screen.getByTestId("metric-strip-skeleton");
    expect(node.querySelectorAll('[data-slot="skeleton"]').length).toBe(12);
  });

  it("forwards className", () => {
    render(<MetricStripSkeleton className="strip-x" />);
    expect(
      screen.getByTestId("metric-strip-skeleton").className,
    ).toMatch(/strip-x/);
  });

  it("guards against negative, non-finite, and fractional count values without throwing", () => {
    // Each of these would throw a RangeError under
    // `Array.from({ length: count })` if not coerced. We assert that the
    // wrapper still mounts (with aria-busy) and renders zero tiles.
    for (const bad of [-1, -100, Number.NaN, Number.POSITIVE_INFINITY]) {
      const { unmount } = render(<MetricStripSkeleton count={bad} />);
      const node = screen.getByTestId("metric-strip-skeleton");
      expect(node).toHaveAttribute("aria-busy", "true");
      expect(node.querySelectorAll('[data-slot="skeleton"]').length).toBe(0);
      unmount();
    }
  });

  it("floors fractional counts (3.7 → 3 tiles → 6 skeletons)", () => {
    render(<MetricStripSkeleton count={3.7} />);
    const node = screen.getByTestId("metric-strip-skeleton");
    expect(node.querySelectorAll('[data-slot="skeleton"]').length).toBe(6);
  });
});
