import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AxiosError, type AxiosResponse } from 'axios';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import Home from '../Home';

const { apiGetMock, getCurrentRegimeMock, getDashboardMock, getStocksMock, useAccountBalancesMock } =
  vi.hoisted(() => ({
    apiGetMock: vi.fn(),
    getCurrentRegimeMock: vi.fn(),
    getDashboardMock: vi.fn(),
    getStocksMock: vi.fn(),
    useAccountBalancesMock: vi.fn(),
  }));

const { mockAuthValue } = vi.hoisted(() => ({
  mockAuthValue: {
    user: { id: 1, username: 'alice', email: 'a@b.com', full_name: 'Alice', is_active: true },
    token: 'tok',
    ready: true,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshMe: vi.fn(),
  } as unknown as ReturnType<typeof import('@/context/AuthContext').useAuth>,
}));

vi.mock('@/context/AuthContext', () => ({
  __esModule: true,
  useAuth: () => mockAuthValue,
}));

vi.mock('@/hooks/usePortfolio', () => ({
  __esModule: true,
  useAccountBalances: () => useAccountBalancesMock(),
}));

vi.mock('@/services/api', () => ({
  __esModule: true,
  default: { get: apiGetMock },
  marketDataApi: { getCurrentRegime: getCurrentRegimeMock },
  portfolioApi: {
    getDashboard: getDashboardMock,
    getStocks: getStocksMock,
  },
  unwrapResponse: <T = unknown>(response: unknown, key: string): T[] => {
    const r = response as Record<string, unknown> | undefined;
    const a = (r?.data as Record<string, unknown> | undefined)?.[key];
    const b = r?.[key];
    const val = (Array.isArray(a) ? a : Array.isArray(b) ? b : []) as T[];
    return val;
  },
}));

function makeAxios404(): AxiosError {
  const err = new AxiosError('Not Found');
  err.response = { status: 404, data: {}, headers: {}, statusText: 'Not Found', config: {} as never } as AxiosResponse;
  return err;
}

function mockBalancesOk(rows: unknown[]) {
  useAccountBalancesMock.mockReturnValue({
    data: rows,
    isPending: false,
    isError: false,
    isSuccess: true,
    error: null,
    refetch: vi.fn(),
  });
}

describe('Home page', () => {
  beforeEach(() => {
    cleanup();
    apiGetMock.mockReset();
    getCurrentRegimeMock.mockReset();
    getDashboardMock.mockReset();
    getStocksMock.mockReset();
    useAccountBalancesMock.mockReset();
    mockBalancesOk([{ account_id: 1, broker: 'IBKR', cash_balance: 5_000 }]);
  });

  afterEach(() => {
    cleanup();
  });

  it('renders regime score, trade cards, and portfolio snapshot when all data resolves', async () => {
    getCurrentRegimeMock.mockResolvedValue({
      regime_state: 'R1',
      composite_score: 2.3,
      as_of_date: '2026-04-21',
      regime_multiplier: 1.0,
      max_equity_exposure_pct: 100,
    });
    apiGetMock.mockResolvedValue({
      data: {
        items: [
          { id: 1, symbol: 'AAPL', action: 'buy', score: 8.4, stage_label: '2A', thesis: 'Breakout' },
          { id: 2, symbol: 'NVDA', action: 'buy', score: 7.9, stage_label: '2B' },
          { id: 3, symbol: 'MSFT', action: 'watch', score: 6.5, stage_label: '2A' },
          { id: 4, symbol: 'GOOG', action: 'watch', score: 5.1, stage_label: '2A' },
        ],
      },
    });
    getDashboardMock.mockResolvedValue({
      data: {
        total_value: 125_000,
        day_change: 1_250,
        day_change_pct: 1.02,
        holdings_count: 7,
        summary: {
          total_market_value: 125_000,
          day_change: 1_250,
          day_change_pct: 1.02,
          positions_count: 7,
        },
      },
    });
    getStocksMock.mockResolvedValue({
      data: {
        stocks: [
          {
            id: 1,
            symbol: 'AAPL',
            account_number: 'U1',
            broker: 'IBKR',
            shares: 10,
            current_price: 200,
            market_value: 2_000,
            cost_basis: 1_800,
            average_cost: 180,
            unrealized_pnl: 200,
            unrealized_pnl_pct: 11.1,
          },
        ],
      },
    });

    renderWithProviders(<Home />);

    await waitFor(() => {
      expect(screen.getByText('R1')).toBeInTheDocument();
    });
    expect(screen.getByTestId('home-regime-score')).toHaveTextContent('2.3');

    expect(await screen.findByText('AAPL', { selector: 'span' })).toBeInTheDocument();
    expect(screen.getByText('NVDA')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
    // Only top 3 trade-card tiles rendered (4th suppressed).
    expect(screen.queryByText('GOOG')).not.toBeInTheDocument();

    expect(screen.getByText('Total NAV')).toBeInTheDocument();
    expect(screen.getByText('$125,000')).toBeInTheDocument();
    expect(screen.getByText('Day P&L')).toBeInTheDocument();
    expect(screen.getByText('$1,250')).toBeInTheDocument();
    expect(screen.getByText('Open positions')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('Cash')).toBeInTheDocument();
    expect(screen.getByText('$5,000')).toBeInTheDocument();
  });

  it('shows empty state for trade cards when the endpoint returns 404', async () => {
    getCurrentRegimeMock.mockResolvedValue({
      regime_state: 'R3',
      composite_score: 3.1,
      as_of_date: '2026-04-21',
    });
    apiGetMock.mockRejectedValue(makeAxios404());
    getDashboardMock.mockResolvedValue({
      data: { total_value: 0, summary: { total_market_value: 0, positions_count: 0 } },
    });
    mockBalancesOk([]);
    getStocksMock.mockResolvedValue({ data: { stocks: [] } });

    renderWithProviders(<Home />);

    await waitFor(() => {
      expect(screen.getByText('No cards yet today')).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Trade cards arrive here when candidates score/i),
    ).toBeInTheDocument();
  });

  it('shows an error card for the portfolio snapshot when balances fail even if the dashboard succeeds', async () => {
    getCurrentRegimeMock.mockResolvedValue({
      regime_state: 'R1',
      composite_score: 2.0,
      as_of_date: '2026-04-21',
    });
    apiGetMock.mockResolvedValue({ data: { items: [] } });
    getDashboardMock.mockResolvedValue({
      data: { total_value: 100, summary: { total_market_value: 100, positions_count: 1 } },
    });
    useAccountBalancesMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      isSuccess: false,
      error: new Error('balances 500'),
      refetch: vi.fn(),
    });
    getStocksMock.mockResolvedValue({ data: { stocks: [] } });

    renderWithProviders(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Couldn't load accounts")).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('shows an error card for the regime section when the regime query fails', async () => {
    getCurrentRegimeMock.mockRejectedValue(new Error('network down'));
    apiGetMock.mockResolvedValue({ data: { items: [] } });
    getDashboardMock.mockResolvedValue({ data: { summary: {} } });
    mockBalancesOk([]);
    getStocksMock.mockResolvedValue({ data: { stocks: [] } });

    renderWithProviders(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Couldn't load market regime")).toBeInTheDocument();
    });
    // Error card renders a retry button — not blank "0".
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('shows loading skeletons for every section before any query resolves', () => {
    getCurrentRegimeMock.mockReturnValue(new Promise(() => {}));
    apiGetMock.mockReturnValue(new Promise(() => {}));
    getDashboardMock.mockReturnValue(new Promise(() => {}));
    getStocksMock.mockReturnValue(new Promise(() => {}));
    useAccountBalancesMock.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      isSuccess: false,
      error: null,
      refetch: vi.fn(),
    });

    const { container } = renderWithProviders(<Home />);

    expect(screen.getByText('Market regime')).toBeInTheDocument();
    expect(screen.getByText("Today's trade cards")).toBeInTheDocument();
    expect(screen.getByText('Portfolio snapshot')).toBeInTheDocument();
    expect(screen.getByText('Open positions vs plan')).toBeInTheDocument();

    const skeletons = container.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
