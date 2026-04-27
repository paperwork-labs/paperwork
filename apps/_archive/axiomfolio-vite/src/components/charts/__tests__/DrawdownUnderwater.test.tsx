import * as React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const setDataMock = vi.fn();
const createChartMock = vi.fn();
const removeMock = vi.fn();

vi.mock("lightweight-charts", () => {
  const stubSeries = () => ({ setData: setDataMock, applyOptions: vi.fn() });
  return {
    BaselineSeries: { __kind: "Baseline" },
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

import { maxDrawdownFromPath } from "@/lib/portfolioDrawdownMath";
import { ColorModeProvider } from "../../../theme/colorMode";
import { DrawdownUnderwater } from "../DrawdownUnderwater";

function renderWithTheme(ui: React.ReactElement) {
  return render(<ColorModeProvider>{ui}</ColorModeProvider>);
}

describe("DrawdownUnderwater", () => {
  beforeEach(() => {
    setDataMock.mockClear();
    createChartMock.mockClear();
    removeMock.mockClear();
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      value: 400,
    });
  });

  it("computes max drawdown for a simple value path", () => {
    const m = maxDrawdownFromPath([100, 110, 95, 120]);
    expect(m).toBeCloseTo((95 - 110) / 110, 5);
  });

  it("renders loading state", () => {
    renderWithTheme(
      <DrawdownUnderwater
        isPending
        isError={false}
        error={null}
        onRetry={() => {}}
        data={undefined}
      />,
    );
    expect(screen.getByTestId("drawdown-underwater-loading")).toBeInTheDocument();
  });

  it("renders error state", () => {
    renderWithTheme(
      <DrawdownUnderwater
        isPending={false}
        isError
        error={new Error("x")}
        onRetry={() => {}}
        data={undefined}
      />,
    );
    expect(screen.getByTestId("drawdown-underwater-error")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    renderWithTheme(
      <DrawdownUnderwater
        isPending={false}
        isError={false}
        error={null}
        onRetry={() => {}}
        data={[]}
      />,
    );
    expect(screen.getByTestId("drawdown-underwater-empty")).toBeInTheDocument();
  });

  it("renders data state with chart container", () => {
    const { container } = renderWithTheme(
      <DrawdownUnderwater
        isPending={false}
        isError={false}
        error={null}
        onRetry={() => {}}
        data={[
          { date: "2024-01-01", total_value: 100 },
          { date: "2024-01-02", total_value: 95 },
        ]}
      />,
    );
    expect(container.querySelector('[data-testid="drawdown-underwater-canvas"]')).toBeTruthy();
  });
});
