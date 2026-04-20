import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { TreemapSkeleton } from "../TreemapSkeleton";

describe("TreemapSkeleton", () => {
  it("renders an aria-busy region with a screen-reader loading message", () => {
    render(<TreemapSkeleton label="holdings allocation" />);
    const node = screen.getByTestId("treemap-skeleton");
    expect(node).toHaveAttribute("aria-busy", "true");
    expect(node).toHaveAttribute("aria-live", "polite");
    expect(
      screen.getByText(/loading holdings allocation/i),
    ).toBeInTheDocument();
  });

  it("renders the deterministic 4×3 grid (3 rows total: 3 + 4 + 4 tiles)", () => {
    render(<TreemapSkeleton />);
    const node = screen.getByTestId("treemap-skeleton");
    // 11 child Skeletons across the 3 rows in our weight matrix.
    const skeletons = node.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBe(11);
  });

  it("forwards className and respects the height prop", () => {
    render(<TreemapSkeleton className="treemap-x" height={500} />);
    const node = screen.getByTestId("treemap-skeleton");
    expect(node.className).toMatch(/treemap-x/);
    expect(node.style.height).toBe("500px");
  });
});
