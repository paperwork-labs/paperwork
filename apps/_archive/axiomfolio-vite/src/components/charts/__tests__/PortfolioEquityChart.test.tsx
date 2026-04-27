import * as React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const setDataMock = vi.fn();
const createChartMock = vi.fn();
const removeMock = vi.fn();

vi.mock("lightweight-charts", () => {
  const stubSeries = () => ({ setData: setDataMock, applyOptions: vi.fn() });
  return {
    AreaSeries: { __kind: "Area" },
    LineSeries: { __kind: "Line" },
    LineStyle: { Dotted: 1, Dashed: 2, Solid: 0 },
    createChart: () => {
      createChartMock();
      return {
        addSeries: () => stubSeries(),
        applyOptions: vi.fn(),
        timeScale: () => ({ fitContent: vi.fn() }),
        remove: removeMock,
      };
    },
  };
});

import { ColorModeProvider } from "../../../theme/colorMode";
import { PortfolioEquityChart } from "../PortfolioEquityChart";

function renderWithTheme(ui: React.ReactElement) {
  return render(<ColorModeProvider>{ui}</ColorModeProvider>);
}

const t0 = 1_704_067_200 as import("lightweight-charts").UTCTimestamp;
const pts = [
  { time: t0, equity: 100, benchmark: 100 as number | null },
  { time: (t0 + 86_400) as import("lightweight-charts").UTCTimestamp, equity: 110, benchmark: 102 },
];

describe("PortfolioEquityChart", () => {
  beforeEach(() => {
    setDataMock.mockClear();
    createChartMock.mockClear();
    removeMock.mockClear();
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      width: 400,
      height: 280,
      top: 0,
      left: 0,
      bottom: 280,
      right: 400,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    } as DOMRect);
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      value: 400,
    });
  });

  it("renders loading state", () => {
    renderWithTheme(
      <PortfolioEquityChart
        isPending
        isError={false}
        error={null}
        onRetry={() => {}}
        data={undefined}
        chartPoints={[]}
        hasBenchmark={false}
        valueMode="usd"
        onValueModeChange={() => {}}
      />,
    );
    expect(screen.getByTestId("portfolio-equity-loading")).toBeInTheDocument();
    expect(createChartMock).not.toHaveBeenCalled();
  });

  it("renders error state", () => {
    renderWithTheme(
      <PortfolioEquityChart
        isPending={false}
        isError
        error={new Error("x")}
        onRetry={() => {}}
        data={undefined}
        chartPoints={[]}
        hasBenchmark={false}
        valueMode="usd"
        onValueModeChange={() => {}}
      />,
    );
    expect(screen.getByTestId("portfolio-equity-error")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    renderWithTheme(
      <PortfolioEquityChart
        isPending={false}
        isError={false}
        error={null}
        onRetry={() => {}}
        data={[]}
        chartPoints={[]}
        hasBenchmark={false}
        valueMode="usd"
        onValueModeChange={() => {}}
      />,
    );
    expect(screen.getByTestId("portfolio-equity-empty")).toBeInTheDocument();
  });

  it("renders data state and builds chart with series (marker path reserved for C4)", async () => {
    const { container } = renderWithTheme(
      <PortfolioEquityChart
        isPending={false}
        isError={false}
        error={null}
        onRetry={() => {}}
        data={[{ date: "2024-01-01", total_value: 100 }]}
        chartPoints={pts}
        hasBenchmark
        valueMode="usd"
        onValueModeChange={() => {}}
      />,
    );
    const root = container.querySelector('[data-testid="portfolio-equity-canvas"]');
    expect(root).toBeTruthy();
    expect(screen.getByTestId("portfolio-equity-chart-data")).toBeInTheDocument();
    await waitFor(() => {
      expect(createChartMock).toHaveBeenCalled();
    });
  });
});
