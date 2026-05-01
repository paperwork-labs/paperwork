import { cleanup, render, screen, act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HqStatCard } from "./HqStatCard";

function stubMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation(() => ({
      matches,
      media: "(prefers-reduced-motion: reduce)",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
      onchange: null,
    })),
  });
}

afterEach(() => {
  cleanup();
});

describe("HqStatCard", () => {
  it("renders label and value", () => {
    stubMatchMedia(true);
    render(<HqStatCard label="Total" value={12} variant="compact" />);
    expect(screen.getByTestId("hq-stat-card")).toBeTruthy();
    expect(screen.getByText("Total")).toBeTruthy();
    expect(screen.getByTestId("hq-stat-value").textContent).toBe("12");
  });

  it("maps status variants to data attribute", () => {
    stubMatchMedia(true);
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
    stubMatchMedia(true);
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

  it("animates numeric value from 0 toward target with requestAnimationFrame", () => {
    stubMatchMedia(false);
    const queue: FrameRequestCallback[] = [];
    let id = 0;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      queue.push(cb);
      return ++id;
    });
    vi.stubGlobal(
      "cancelAnimationFrame",
      vi.fn((_handle: number) => {
        /* noop — tests drain queue explicitly */
      }),
    );

    render(<HqStatCard label="N" value={100} variant="compact" />);
    expect(screen.getByTestId("hq-stat-value").textContent).toBe("0");

    const start = 1_000;
    act(() => {
      queue.shift()?.(start);
    });
    act(() => {
      queue.shift()?.(start + 300);
    });
    expect(Number(screen.getByTestId("hq-stat-value").textContent)).toBeGreaterThan(0);
    expect(Number(screen.getByTestId("hq-stat-value").textContent)).toBeLessThan(100);

    act(() => {
      queue.shift()?.(start + 600);
    });
    expect(screen.getByTestId("hq-stat-value").textContent).toBe("100");

    vi.unstubAllGlobals();
  });

  it("respects prefers-reduced-motion (no interim frames)", () => {
    stubMatchMedia(true);
    const rafSpy = vi.fn();
    vi.stubGlobal("requestAnimationFrame", rafSpy);

    render(<HqStatCard label="N" value={42} variant="compact" />);
    expect(screen.getByTestId("hq-stat-value").textContent).toBe("42");
    expect(rafSpy).not.toHaveBeenCalled();

    vi.unstubAllGlobals();
  });

  it("does not animate string values", () => {
    stubMatchMedia(false);
    const rafSpy = vi.fn();
    vi.stubGlobal("requestAnimationFrame", rafSpy);

    render(<HqStatCard label="Ratio" value="3/10" variant="compact" />);
    expect(screen.getByTestId("hq-stat-value").textContent).toBe("3/10");
    expect(rafSpy).not.toHaveBeenCalled();

    vi.unstubAllGlobals();
  });

  it("renders as a button with aria-pressed when interactive", () => {
    stubMatchMedia(true);
    render(
      <HqStatCard
        label="Completed"
        value={5}
        variant="compact"
        status="success"
        onClick={() => {}}
        selected
      />,
    );
    const btn = screen.getByRole("button", { name: /completed/i });
    expect(btn.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("hq-stat-value").textContent).toBe("5");
  });
});
