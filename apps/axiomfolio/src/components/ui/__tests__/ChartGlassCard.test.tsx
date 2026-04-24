import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { ChartGlassCard } from "../ChartGlassCard";

describe("ChartGlassCard", () => {
  it("renders children inside a region with the resting elevation by default", () => {
    render(
      <ChartGlassCard ariaLabel="Holding price chart">
        <span>chart content</span>
      </ChartGlassCard>,
    );
    const card = screen.getByRole("region", { name: /holding price chart/i });
    expect(card).toBeInTheDocument();
    expect(card.dataset.level).toBe("resting");
    expect(card).toHaveTextContent("chart content");
  });

  it("applies the requested elevation level via data attribute", () => {
    render(
      <ChartGlassCard ariaLabel="Treemap" level="floating">
        <span>treemap</span>
      </ChartGlassCard>,
    );
    expect(screen.getByRole("region", { name: /treemap/i }).dataset.level).toBe(
      "floating",
    );
  });

  it("opts into glass / interactive / padding variants", () => {
    render(
      <ChartGlassCard
        ariaLabel="Equity curve"
        glass
        interactive
        padding="lg"
        data-testid="glass"
      >
        <span>equity</span>
      </ChartGlassCard>,
    );
    const node = screen.getByTestId("glass");
    expect(node.dataset.glass).toBe("true");
    expect(node.className).toMatch(/backdrop-blur-xl/);
    expect(node.className).toMatch(/p-8/);
    expect(node.className).toMatch(/transition-shadow/);
  });

  it("omits the role when no ariaLabel is supplied so callers can wrap their own region", () => {
    render(
      <ChartGlassCard data-testid="card">
        <span>plain</span>
      </ChartGlassCard>,
    );
    const card = screen.getByTestId("card");
    expect(card.getAttribute("role")).toBeNull();
  });

  it("forwards refs and arbitrary HTML props", () => {
    const ref = { current: null as HTMLDivElement | null };
    render(
      <ChartGlassCard ref={ref} id="metric-strip" data-foo="bar">
        <span />
      </ChartGlassCard>,
    );
    expect(ref.current).not.toBeNull();
    expect(ref.current?.id).toBe("metric-strip");
    expect(ref.current?.getAttribute("data-foo")).toBe("bar");
  });
});
