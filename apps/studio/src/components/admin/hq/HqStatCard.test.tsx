import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { HqStatCard } from "./HqStatCard";

afterEach(() => {
  cleanup();
});

describe("HqStatCard", () => {
  it("renders label and value", () => {
    render(<HqStatCard label="Total" value={12} variant="compact" />);
    expect(screen.getByTestId("hq-stat-card")).toBeTruthy();
    expect(screen.getByText("Total")).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy();
  });

  it("maps status variants to data attribute", () => {
    const { rerender } = render(
      <HqStatCard label="Blocked" value={1} status="danger" variant="default" />,
    );
    const card = screen.getByTestId("hq-stat-card");
    expect(card.getAttribute("data-hq-stat-status")).toBe("danger");
    rerender(<HqStatCard label="OK" value={2} status="success" variant="default" />);
    expect(screen.getByTestId("hq-stat-card").getAttribute("data-hq-stat-status")).toBe(
      "success",
    );
  });

  it("renders delta when provided", () => {
    render(
      <HqStatCard
        label="X"
        value={1}
        delta={{ direction: "up", value: "+3" }}
        variant="default"
      />,
    );
    expect(screen.getByText("+3")).toBeTruthy();
  });
});
