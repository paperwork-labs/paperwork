import * as React from "react";
import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";

import {
  ChartCrosshair,
  useCrosshairTracking,
} from "../ChartCrosshair";

describe("ChartCrosshair", () => {
  it("returns null when both x and y are null", () => {
    const { container } = render(
      <ChartCrosshair width={400} height={200} x={null} y={null} />,
    );
    expect(container.querySelector("svg")).toBeNull();
  });

  it("renders an SVG with both lines when x and y are set", () => {
    const { container } = render(
      <ChartCrosshair width={400} height={200} x={100} y={50} />,
    );
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    const lines = container.querySelectorAll("line");
    expect(lines).toHaveLength(2);
  });

  it("only renders the vertical line when showHorizontal is false", () => {
    const { container } = render(
      <ChartCrosshair
        width={400}
        height={200}
        x={100}
        y={50}
        showHorizontal={false}
      />,
    );
    const lines = container.querySelectorAll("line");
    expect(lines).toHaveLength(1);
    expect(lines[0].getAttribute("x1")).toBe("100");
  });

  it("uses the explicit color prop when supplied", () => {
    const { container } = render(
      <ChartCrosshair
        width={400}
        height={200}
        x={100}
        y={50}
        color="#ff0000"
      />,
    );
    const line = container.querySelector("line");
    expect(line?.getAttribute("stroke")).toBe("#ff0000");
  });

  it("reads --chart-axis (the actual token) and wraps space-separated rgb", () => {
    const realGCS = window.getComputedStyle;
    const spy = vi
      .spyOn(window, "getComputedStyle")
      .mockImplementation((el: Element, pseudo?: string | null) => {
        const real = realGCS(el, pseudo ?? null);
        return {
          ...real,
          getPropertyValue: (prop: string) => {
            if (prop === "--chart-axis") return " 15 23 42 / 0.35 ";
            if (prop === "--axis") return "";
            return real.getPropertyValue(prop);
          },
        } as CSSStyleDeclaration;
      });

    const { container } = render(
      <ChartCrosshair width={400} height={200} x={100} y={50} />,
    );
    const line = container.querySelector("line");
    // Wraps the raw token with rgb(...) so it's a valid color string.
    expect(line?.getAttribute("stroke")).toBe("rgb(15 23 42 / 0.35)");
    spy.mockRestore();
  });

  it("subscribes to the axiomfolio:color-palette-change event", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = render(
      <ChartCrosshair width={400} height={200} x={100} y={50} />,
    );
    const eventNames = addSpy.mock.calls.map((c) => c[0]);
    expect(eventNames).toContain("axiomfolio:color-palette-change");
    expect(eventNames).not.toContain("palettechange");
    unmount();
    const removed = removeSpy.mock.calls.map((c) => c[0]);
    expect(removed).toContain("axiomfolio:color-palette-change");
    addSpy.mockRestore();
    removeSpy.mockRestore();
  });

  it("renders the announceText for screen readers", () => {
    const { container } = render(
      <ChartCrosshair
        width={400}
        height={200}
        x={100}
        y={50}
        announceText="AAPL closed at $192.34"
      />,
    );
    // Live region is now rendered as a SIBLING of the SVG (not inside
    // <foreignObject>) so it survives the SVG's `aria-hidden` attribute
    // and is reliably announced by AT. It should be queryable via role
    // since it's a regular HTML element now.
    const liveByRole = container.querySelector('[role="status"]');
    expect(liveByRole).not.toBeNull();
    expect(liveByRole?.textContent).toContain("$192.34");
    expect(liveByRole?.getAttribute("aria-live")).toBe("polite");
    expect(liveByRole?.classList.contains("sr-only-live")).toBe(true);
    // And it must NOT be a descendant of an aria-hidden subtree.
    const hiddenAncestor = liveByRole?.closest('[aria-hidden="true"]');
    expect(hiddenAncestor).toBeNull();
  });
});

describe("useCrosshairTracking", () => {
  it("starts with null coordinates", () => {
    const { result } = renderHook(() => useCrosshairTracking());
    expect(result.current.x).toBeNull();
    expect(result.current.y).toBeNull();
  });

  it("updates coords on mouse move and clears on leave", () => {
    function Harness() {
      const { x, y, onMouseMove, onMouseLeave } = useCrosshairTracking();
      return (
        <div
          data-testid="container"
          style={{ width: 400, height: 200 }}
          onMouseMove={onMouseMove}
          onMouseLeave={onMouseLeave}
        >
          <span data-testid="coords">{`${x ?? "null"}:${y ?? "null"}`}</span>
        </div>
      );
    }
    render(<Harness />);
    const container = screen.getByTestId("container");
    Object.defineProperty(container, "getBoundingClientRect", {
      value: () =>
        ({
          left: 0,
          top: 0,
          right: 400,
          bottom: 200,
          width: 400,
          height: 200,
          x: 0,
          y: 0,
          toJSON: () => ({}),
        }) as DOMRect,
    });
    act(() => {
      fireEvent.mouseMove(container, { clientX: 120, clientY: 64 });
    });
    expect(screen.getByTestId("coords").textContent).toBe("120:64");
    act(() => {
      fireEvent.mouseLeave(container);
    });
    expect(screen.getByTestId("coords").textContent).toBe("null:null");
  });

  it("clamps to null when pointer is outside the rect", () => {
    function Harness() {
      const { x, y, onMouseMove } = useCrosshairTracking();
      return (
        <div
          data-testid="container"
          style={{ width: 200, height: 100 }}
          onMouseMove={onMouseMove}
        >
          <span data-testid="coords">{`${x ?? "null"}:${y ?? "null"}`}</span>
        </div>
      );
    }
    render(<Harness />);
    const container = screen.getByTestId("container");
    Object.defineProperty(container, "getBoundingClientRect", {
      value: () =>
        ({
          left: 0,
          top: 0,
          right: 200,
          bottom: 100,
          width: 200,
          height: 100,
          x: 0,
          y: 0,
          toJSON: () => ({}),
        }) as DOMRect,
    });
    act(() => {
      fireEvent.mouseMove(container, { clientX: 500, clientY: 500 });
    });
    expect(screen.getByTestId("coords").textContent).toBe("null:null");
  });
});
