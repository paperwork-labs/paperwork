import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { EquityCurveSkeleton } from "../EquityCurveSkeleton";

describe("EquityCurveSkeleton", () => {
  it("renders an aria-busy region with a screen-reader loading message", () => {
    render(<EquityCurveSkeleton />);
    const node = screen.getByTestId("equity-curve-skeleton");
    expect(node).toHaveAttribute("aria-busy", "true");
    expect(node).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText(/loading equity curve/i)).toBeInTheDocument();
  });

  it("respects the height prop and splits into a 2/3 + 1/3 layout", () => {
    render(<EquityCurveSkeleton height={300} />);
    const node = screen.getByTestId("equity-curve-skeleton");
    expect(node.style.height).toBe("300px");
  });

  it("accepts a custom label and className", () => {
    render(
      <EquityCurveSkeleton label="strategy P&L" className="my-class" />,
    );
    expect(screen.getByText(/loading strategy p&l/i)).toBeInTheDocument();
    expect(
      screen.getByTestId("equity-curve-skeleton").className,
    ).toMatch(/my-class/);
  });

  it("anchors the bottom-most grid line of both panels via `bottom: 0`", () => {
    render(<EquityCurveSkeleton />);
    const equityBottom = screen.getByTestId("equity-curve-skeleton-grid-g4");
    const drawdownBottom = screen.getByTestId("equity-curve-skeleton-grid-d2");
    expect(equityBottom.style.bottom).toBe("0px");
    expect(equityBottom.style.top).toBe("");
    expect(drawdownBottom.style.bottom).toBe("0px");
    expect(drawdownBottom.style.top).toBe("");
  });
});
