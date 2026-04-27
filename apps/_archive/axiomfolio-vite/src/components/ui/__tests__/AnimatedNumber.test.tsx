import { describe, expect, it, vi, afterEach } from "vitest";
import { act, render, screen } from "@testing-library/react";

vi.mock("framer-motion", async () => {
  const actual = await vi.importActual<typeof import("framer-motion")>(
    "framer-motion",
  );
  return {
    ...actual,
    useReducedMotion: vi.fn(() => false),
  };
});

import { useReducedMotion } from "framer-motion";
import { AnimatedNumber } from "../AnimatedNumber";

const useReducedMotionMock = vi.mocked(useReducedMotion);

afterEach(() => {
  useReducedMotionMock.mockReturnValue(false);
  vi.useRealTimers();
});

describe("AnimatedNumber", () => {
  it("renders the formatted initial value with tabular-nums", () => {
    render(<AnimatedNumber value={1234.5} />);
    const node = screen.getByTestId("animated-number");
    expect(node.className).toMatch(/tabular-nums/);
    expect(node.className).toMatch(/\bnum\b/);
    expect(node).toHaveTextContent(/1,234\.5/);
  });

  it("applies a custom formatter and aria-label", () => {
    render(
      <AnimatedNumber
        value={0.1234}
        format={(n) => `${(n * 100).toFixed(2)}%`}
        ariaLabel="growth rate"
      />,
    );
    const node = screen.getByTestId("animated-number");
    expect(node).toHaveTextContent("12.34%");
    expect(node).toHaveAttribute("aria-label", "growth rate");
  });

  it("falls back to the formatted value as the default aria-label", () => {
    render(<AnimatedNumber value={42} />);
    expect(screen.getByTestId("animated-number")).toHaveAttribute(
      "aria-label",
      "42",
    );
  });

  it("snaps immediately to the new value under reduced motion", () => {
    useReducedMotionMock.mockReturnValue(true);
    const { rerender } = render(<AnimatedNumber value={100} />);
    expect(screen.getByTestId("animated-number")).toHaveTextContent("100");
    act(() => {
      rerender(<AnimatedNumber value={500} />);
    });
    expect(screen.getByTestId("animated-number")).toHaveTextContent("500");
    expect(screen.getByTestId("animated-number")).toHaveAttribute(
      "aria-label",
      "500",
    );
  });

  it("forwards a custom className", () => {
    render(<AnimatedNumber value={1} className="text-xl text-primary" />);
    const node = screen.getByTestId("animated-number");
    expect(node.className).toMatch(/text-xl/);
    expect(node.className).toMatch(/text-primary/);
  });
});
