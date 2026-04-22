import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import Home from '../Home';

/*
 * J4 Home reboot — tests the composed page renders each section without
 * 4xx/5xx in the happy path and surfaces the "Connect a broker" CTA when no
 * broker has been linked. Fine-grained behavior is covered by unit tests:
 *   - utils/greeting.test.ts
 *   - hooks/__tests__/useHomeAttention.test.ts
 * Plus component-level rendering is exercised by the Ladle stories.
 */

const {
  getCurrentRegimeMock,
  getDashboardMock,
  useAccountBalancesMock,
  usePositionsMock,
  useDividendSummaryMock,
  usePnlSummaryMock,
  usePortfolioPerformanceHistoryMock,
  usePortfolioInsightsMock,
  useRiskMetricsMock,
} = vi.hoisted(() => ({
  getCurrentRegimeMock: vi.fn(),
  getDashboardMock: vi.fn(),
  useAccountBalancesMock: vi.fn(),
  usePositionsMock: vi.fn(),
  useDividendSummaryMock: vi.fn(),
  usePnlSummaryMock: vi.fn(),
  usePortfolioPerformanceHistoryMock: vi.fn(),
  usePortfolioInsightsMock: vi.fn(),
  useRiskMetricsMock: vi.fn(),
}));

const { mockAuthValue } = vi.hoisted(() => ({
  mockAuthValue: {
    user: {
      id: 1,
      username: 'alice',
      email: 'a@b.com',
      full_name: 'Alice Liddell',
      is_active: true,
      currency_preference: 'USD',
    },
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
  usePositions: () => usePositionsMock(),
  useDividendSummary: () => useDividendSummaryMock(),
  usePnlSummary: () => usePnlSummaryMock(),
  usePortfolioPerformanceHistory: () => usePortfolioPerformanceHistoryMock(),
  usePortfolioInsights: () => usePortfolioInsightsMock(),
  useRiskMetrics: () => useRiskMetricsMock(),
}));

vi.mock('@/services/api', () => ({
  __esModule: true,
  default: { get: vi.fn() },
  marketDataApi: { getCurrentRegime: getCurrentRegimeMock },
  portfolioApi: {
    getDashboard: getDashboardMock,
    getStocks: vi.fn(),
    getPnlSummary: vi.fn(),
    getBalances: vi.fn(),
    getPerformanceHistory: vi.fn(),
    getDividendSummary: vi.fn(),
    getInsights: vi.fn(),
    getRiskMetrics: vi.fn(),
  },
  unwrapResponse: <T = unknown>(response: unknown, key: string): T[] => {
    const r = response as Record<string, unknown> | undefined;
    const a = (r?.data as Record<string, unknown> | undefined)?.[key];
    const b = r?.[key];
    const val = (Array.isArray(a) ? a : Array.isArray(b) ? b : []) as T[];
    return val;
  },
}));

interface QueryShape {
  data: unknown;
  isPending?: boolean;
  isError?: boolean;
  isSuccess?: boolean;
  error?: unknown;
}

function queryOk<T>(data: T): QueryShape {
  return {
    data,
    isPending: false,
    isError: false,
    isSuccess: true,
    error: null,
  };
}

function queryLoading(): QueryShape {
  return { data: undefined, isPending: true, isError: false, isSuccess: false, error: null };
}

function queryErr(err: unknown): QueryShape {
  return { data: undefined, isPending: false, isError: true, isSuccess: false, error: err };
}

function attachRefetch(q: QueryShape): QueryShape & { refetch: () => void } {
  return { ...q, refetch: vi.fn() };
}

function primeBrokersOk(rows: unknown[]) {
  useAccountBalancesMock.mockReturnValue(attachRefetch(queryOk(rows)));
}

describe('Home page (J4)', () => {
  beforeEach(() => {
    cleanup();
    getCurrentRegimeMock.mockReset();
    getDashboardMock.mockReset();
    useAccountBalancesMock.mockReset();
    usePositionsMock.mockReset();
    useDividendSummaryMock.mockReset();
    usePnlSummaryMock.mockReset();
    usePortfolioPerformanceHistoryMock.mockReset();
    usePortfolioInsightsMock.mockReset();
    useRiskMetricsMock.mockReset();

    primeBrokersOk([{ account_id: 1, broker: 'IBKR', cash_balance: 5_000 }]);
    usePositionsMock.mockReturnValue(attachRefetch(queryOk([])));
    useDividendSummaryMock.mockReturnValue(attachRefetch(queryOk({})));
    usePnlSummaryMock.mockReturnValue(
      attachRefetch(
        queryOk({
          unrealized_pnl: 0,
          realized_pnl: 0,
          total_dividends: 0,
          total_fees: 0,
          total_return: 0,
        }),
      ),
    );
    usePortfolioPerformanceHistoryMock.mockReturnValue(attachRefetch(queryOk([])));
    usePortfolioInsightsMock.mockReturnValue(attachRefetch(queryOk(null)));
    useRiskMetricsMock.mockReturnValue(attachRefetch(queryOk({})));

    getCurrentRegimeMock.mockResolvedValue({
      regime_state: 'R1',
      composite_score: 2.3,
      as_of_date: '2026-04-21',
    });
    getDashboardMock.mockResolvedValue({
      data: {
        total_value: 125_000,
        day_change: 1_250,
        day_change_pct: 1.02,
        summary: {
          total_market_value: 125_000,
          day_change: 1_250,
          day_change_pct: 1.02,
          positions_count: 7,
        },
      },
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders hero + nerve center + your book + quiet footer in the happy path', async () => {
    usePositionsMock.mockReturnValue(
      attachRefetch(
        queryOk([
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
            stage_label: '2A',
          },
        ]),
      ),
    );

    renderWithProviders(<Home />);

    expect(await screen.findByText('Total NAV')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText('$125,000').length).toBeGreaterThan(0);
    });

    expect(screen.getByText(/Alice/)).toBeInTheDocument();
    expect(screen.getAllByText('Nerve center').length).toBeGreaterThan(0);
    expect(screen.getByText(/Everything's steady/i)).toBeInTheDocument();

    expect(screen.getAllByText('Your book').length).toBeGreaterThan(0);
    const aaplMatches = await screen.findAllByText('AAPL');
    expect(aaplMatches.length).toBeGreaterThan(0);

    expect(screen.getByText('YTD Income')).toBeInTheDocument();
    expect(screen.getByText('YTD Realized')).toBeInTheDocument();
    expect(screen.getByText('Portfolio Heat')).toBeInTheDocument();
    expect(screen.getByText('Concentration Top-5')).toBeInTheDocument();
  });

  it('surfaces "Connect a broker" CTA in the hero when no brokers are present', async () => {
    primeBrokersOk([]);

    renderWithProviders(<Home />);

    await waitFor(() => {
      expect(screen.getByText('Connect a broker to see your book')).toBeInTheDocument();
    });
    expect(screen.getAllByRole('button', { name: /connect a broker/i }).length).toBeGreaterThan(0);
  });

  it('shows an error card in the hero when the balances query fails', async () => {
    useAccountBalancesMock.mockReturnValue(attachRefetch(queryErr(new Error('balances 500'))));

    renderWithProviders(<Home />);

    await waitFor(() => {
      expect(screen.getAllByText(/Couldn't load accounts/i).length).toBeGreaterThan(0);
    });
    expect(screen.getAllByRole('button', { name: /try again/i }).length).toBeGreaterThan(0);
  });

  it('shows loading skeletons before any query resolves', () => {
    useAccountBalancesMock.mockReturnValue(attachRefetch(queryLoading()));
    usePositionsMock.mockReturnValue(attachRefetch(queryLoading()));
    useDividendSummaryMock.mockReturnValue(attachRefetch(queryLoading()));
    usePnlSummaryMock.mockReturnValue(attachRefetch(queryLoading()));
    usePortfolioPerformanceHistoryMock.mockReturnValue(attachRefetch(queryLoading()));
    usePortfolioInsightsMock.mockReturnValue(attachRefetch(queryLoading()));
    useRiskMetricsMock.mockReturnValue(attachRefetch(queryLoading()));
    getCurrentRegimeMock.mockReturnValue(new Promise(() => {}));
    getDashboardMock.mockReturnValue(new Promise(() => {}));

    const { container } = renderWithProviders(<Home />);

    expect(screen.getByText('Nerve center')).toBeInTheDocument();
    expect(screen.getByText('Your book')).toBeInTheDocument();
    const skeletons = container.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
