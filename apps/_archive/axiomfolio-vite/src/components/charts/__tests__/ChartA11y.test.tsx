import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

import { ChartAnnouncer } from "../ChartA11y";

afterEach(() => {
  vi.useRealTimers();
});

describe("ChartAnnouncer", () => {
  it("renders a polite live region with the initial summary", () => {
    render(<ChartAnnouncer summary="AAPL at $192.34" />);
    const node = screen.getByRole("status");
    expect(node).toHaveAttribute("aria-live", "polite");
    expect(node).toHaveAttribute("aria-atomic", "true");
    expect(node).toHaveTextContent("AAPL at $192.34");
  });

  it("displays the initial summary immediately on mount", () => {
    vi.useFakeTimers();
    render(<ChartAnnouncer summary="initial value" throttleMs={500} />);
    expect(screen.getByTestId("chart-announcer")).toHaveTextContent(
      "initial value",
    );
  });

  it("throttles rapid updates and keeps the last one in the window", () => {
    vi.useFakeTimers();
    function Harness({ summary }: { summary: string }) {
      return <ChartAnnouncer summary={summary} throttleMs={500} />;
    }
    const { rerender } = render(<Harness summary="initial" />);
    expect(screen.getByTestId("chart-announcer")).toHaveTextContent("initial");

    // Within the throttle window, updates buffer to the most recent value.
    act(() => {
      rerender(<Harness summary="rapid-1" />);
      vi.advanceTimersByTime(50);
      rerender(<Harness summary="rapid-2" />);
      vi.advanceTimersByTime(50);
      rerender(<Harness summary="rapid-3" />);
    });
    // Still showing the initial value because we're inside the window.
    expect(screen.getByTestId("chart-announcer")).toHaveTextContent("initial");

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(screen.getByTestId("chart-announcer")).toHaveTextContent("rapid-3");
  });
});
