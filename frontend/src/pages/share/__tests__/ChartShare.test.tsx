import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import axios from "axios";

import { ColorModeProvider } from "@/theme/colorMode";

import ChartShare from "../ChartShare";

const mockBars = vi.fn();

vi.mock("@/services/chartShare", () => ({
  fetchPublicShareChartBars: (...args: unknown[]) => mockBars(...args),
}));

vi.mock("@/components/charts/SymbolChartWithMarkers", () => ({
  __esModule: true,
  default: function MockChart() {
    return <div data-testid="mock-shared-chart" />;
  },
  defaultIndicators: () => ({
    trendLines: true,
    gaps: true,
    tdSequential: true,
    emas: true,
    stage: true,
    supportResistance: true,
  }),
}));

describe("ChartShare", () => {
  beforeEach(() => {
    mockBars.mockReset();
  });

  it("shows loading then chart when bars load", async () => {
    mockBars.mockResolvedValue({
      symbol: "AAPL",
      period: "1y",
      interval: "1d",
      data_source: "test",
      indicators: ["emas"],
      bars: [
        {
          time: "2024-01-02T00:00:00",
          open: 10,
          high: 11,
          low: 9,
          close: 10.5,
          volume: 1000,
        },
        {
          time: "2024-01-03T00:00:00",
          open: 10.5,
          high: 12,
          low: 10,
          close: 11.5,
          volume: 1100,
        },
      ],
    });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <ColorModeProvider>
          <MemoryRouter initialEntries={["/share/c/tok"]}>
            <Routes>
              <Route path="/share/c/:token" element={<ChartShare />} />
            </Routes>
          </MemoryRouter>
        </ColorModeProvider>
      </QueryClientProvider>,
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByText(/Shared from AxiomFolio/i)).toBeInTheDocument();
    expect(await screen.findByTestId("mock-shared-chart")).toBeInTheDocument();
    expect(screen.getByText(/Sign up free/i)).toBeInTheDocument();
  });

  it("shows error copy when fetch fails with 401", async () => {
    const err = new axios.AxiosError("401");
    err.response = { status: 401, data: { detail: "expired" } } as typeof err.response;
    mockBars.mockRejectedValue(err);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <ColorModeProvider>
          <MemoryRouter initialEntries={["/share/c/bad"]}>
            <Routes>
              <Route path="/share/c/:token" element={<ChartShare />} />
            </Routes>
          </MemoryRouter>
        </ColorModeProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/This link expired/i)).toBeInTheDocument();
  });
});
