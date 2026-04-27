import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { PriceChartSkeleton } from "../PriceChartSkeleton";

describe("PriceChartSkeleton", () => {
  it("renders an aria-busy region with a screen-reader loading message", () => {
    render(<PriceChartSkeleton label="AAPL price chart" />);
    const node = screen.getByTestId("price-chart-skeleton");
    expect(node).toHaveAttribute("aria-busy", "true");
    expect(node).toHaveAttribute("aria-live", "polite");
    expect(node).toHaveAttribute("role", "status");
    expect(screen.getByText(/loading aapl price chart/i)).toBeInTheDocument();
  });

  it("respects the height prop", () => {
    render(<PriceChartSkeleton height={500} />);
    const node = screen.getByTestId("price-chart-skeleton");
    expect(node.style.height).toBe("500px");
  });

  it("forwards className", () => {
    render(<PriceChartSkeleton className="custom-class" />);
    expect(
      screen.getByTestId("price-chart-skeleton").className,
    ).toMatch(/custom-class/);
  });

  it("uses the default 'price chart' label when none supplied", () => {
    render(<PriceChartSkeleton />);
    expect(screen.getByText(/loading price chart/i)).toBeInTheDocument();
  });

  it("anchors the bottom-most grid line via `bottom: 0` so it lands flush with the chart edge", () => {
    render(<PriceChartSkeleton />);
    const bottomLine = screen.getByTestId("price-chart-skeleton-grid-g4");
    // Inline style anchors via bottom: 0; never via top: 100% (which would
    // push the border one pixel below the chart's bounds).
    expect(bottomLine.style.bottom).toBe("0px");
    expect(bottomLine.style.top).toBe("");
  });
});
