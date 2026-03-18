import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { SkeletonCard } from "./skeleton-card";

describe("SkeletonCard", () => {
  it("renders with default 3 skeleton lines", () => {
    const { container } = render(<SkeletonCard />);
    const lines = container.querySelectorAll(".animate-pulse");
    expect(lines.length).toBe(4); // 1 title + 3 body lines
  });

  it("renders custom number of lines", () => {
    const { container } = render(<SkeletonCard lines={5} />);
    const lines = container.querySelectorAll(".animate-pulse");
    expect(lines.length).toBe(6); // 1 title + 5 body lines
  });

  it("applies custom className", () => {
    const { container } = render(<SkeletonCard className="mt-4" />);
    expect(container.firstChild).toHaveClass("mt-4");
  });

  it("renders deterministic widths (no randomness)", () => {
    const { container: c1 } = render(<SkeletonCard lines={4} />);
    const { container: c2 } = render(<SkeletonCard lines={4} />);

    const lines1 = Array.from(c1.querySelectorAll(".animate-pulse")).slice(1);
    const lines2 = Array.from(c2.querySelectorAll(".animate-pulse")).slice(1);

    lines1.forEach((line, i) => {
      expect((line as HTMLElement).style.width).toBe(
        (lines2[i] as HTMLElement).style.width
      );
    });
  });
});
