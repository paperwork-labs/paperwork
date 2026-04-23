import React from 'react';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { marketDataApi } from '../../../services/api';
import { renderWithProviders } from '@/test/render';

import OverviewTab from '../tabs/OverviewTab';
import PerformanceTab from '../tabs/PerformanceTab';
import RiskTab from '../tabs/RiskTab';
import AllocationTab from '../tabs/AllocationTab';

const mockUsePortfolio = vi.hoisted(() => ({
  usePortfolioOverview: vi.fn(),
  usePortfolioAccounts: vi.fn(),
  usePositions: vi.fn(),
  usePortfolioSync: vi.fn(),
  usePortfolioInsights: vi.fn(),
  useAccountBalances: vi.fn(),
  useLiveSummary: vi.fn(),
  usePnlSummary: vi.fn(),
  usePortfolioPerformanceHistory: vi.fn(),
  useDividendSummary: vi.fn(),
  useMarginInterest: vi.fn(),
  useRiskMetrics: vi.fn(),
}));

const mockUseAccountFilterImpl = vi.hoisted(() =>
  vi.fn(() => ({
    selectedAccount: 'all' as const,
    setSelectedAccount: vi.fn(),
    filteredData: [] as unknown[],
    accounts: [] as unknown[],
    totalValue: 0,
    totalPnL: 0,
    totalPositions: 0,
    isLoading: false,
    error: null as string | null,
  })),
);

vi.mock('../../../components/portfolio/DailyNarrative', () => ({
  DailyNarrative: () => null,
}));

vi.mock('../../../components/shared/CircuitBreakerBanner', () => ({
  CircuitBreakerBanner: () => null,
}));

vi.mock('../../../hooks/useChartColors', () => ({
  useChartColors: () => ({
    danger: '#dc2626',
    success: '#16a34a',
    neutral: '#3b82f6',
    area1: '#16a34a',
    area2: '#2563eb',
    grid: '#e2e8f0',
    axis: '#64748b',
    refLine: '#e2e8f0',
    muted: '#64748b',
    subtle: '#94a3b8',
    border: '#e2e8f0',
    brand500: '#f59e0b',
    brand400: '#fbbf24',
    brand700: '#d97706',
    warning: '#d97706',
    tooltipBg: '#0f172a',
    tooltipBorder: '#334155',
  }),
}));

vi.mock('../../../hooks/useAccountFilter', () => ({
  useAccountFilter: mockUseAccountFilterImpl,
}));

vi.mock('../../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({ currency: 'USD' as const }),
}));

// OverviewTab / RiskTab now consume AccountContext to scope queries to the
// selected account. The test harness (`renderWithProviders`) intentionally
// stays lean and does NOT wrap with AccountProvider (which would require
// AuthContext + a real /accounts fetch). Stub the hook with an "all" scope
// so the components render the portfolio-wide code path.
vi.mock('../../../context/AccountContext', () => ({
  useAccountContext: () => ({
    accounts: [],
    loading: false,
    error: null,
    selected: 'all' as const,
    setSelected: vi.fn(),
    refetch: vi.fn(),
  }),
}));

vi.mock('../../../hooks/usePortfolio', async () => {
  const actual = await vi.importActual<typeof import('../../../hooks/usePortfolio')>(
    '../../../hooks/usePortfolio',
  );
  return {
    ...actual,
    ...mockUsePortfolio,
  };
});

const mockUsePortfolioAllocation = vi.hoisted(() => vi.fn());

vi.mock('../../../hooks/usePortfolioAllocation', () => ({
  usePortfolioAllocation: (groupBy: string) => mockUsePortfolioAllocation(groupBy),
}));

function setOverviewDefaultMocks() {
  const refetch = vi.fn();
  mockUsePortfolio.usePortfolioAccounts.mockReturnValue({
    data: [{ id: 1, account_number: 'U1234567', broker: 'IBKR' }],
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  } as any);
  mockUsePortfolio.usePortfolioOverview.mockReturnValue({
    summary: {
      data: { data: { summary: { day_change: 0, day_change_pct: 0 } } },
      isPending: false,
      isError: false,
    },
    isPending: false,
    isError: false,
    error: null,
    accountsData: [{ id: 1, account_number: 'U1234567', broker: 'IBKR', last_successful_sync: null as string | null }],
  });
  mockUsePortfolio.usePositions.mockReturnValue({
    data: [],
    isPending: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  } as any);
  mockUsePortfolio.usePortfolioSync.mockReturnValue({ mutate: vi.fn(), isPending: false, isError: false } as any);
  mockUsePortfolio.usePortfolioInsights.mockReturnValue({
    data: null,
    isError: false,
    isPending: false,
    refetch: vi.fn(),
  } as any);
  mockUsePortfolio.useAccountBalances.mockReturnValue({
    data: undefined,
    isPending: false,
    isError: false,
    refetch,
  } as any);
  mockUsePortfolio.useLiveSummary.mockReturnValue({
    data: { is_live: true },
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  } as any);
  mockUsePortfolio.usePnlSummary.mockReturnValue({ data: undefined, isPending: false, isError: false, refetch: vi.fn() } as any);
  mockUsePortfolio.usePortfolioPerformanceHistory.mockReturnValue({
    isPending: true,
    isError: false,
    data: undefined,
    error: null,
    refetch: vi.fn(),
  } as any);
}

describe('OverviewTab', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders when balances data is still undefined (parallel fetches) without throwing', () => {
    setOverviewDefaultMocks();
    expect(() => renderWithProviders(<OverviewTab />)).not.toThrow();
  });
});

describe('PerformanceTab', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  beforeEach(() => {
    vi.spyOn(marketDataApi, 'getHistory').mockResolvedValue({ bars: [] } as any);
  });

  it('shows the chart container after history loads (fixed height, no collapsed -1)', async () => {
    const refetch = vi.fn();
    mockUsePortfolio.usePortfolioPerformanceHistory.mockReturnValue({
      isPending: false,
      isError: false,
      isSuccess: true,
      data: [{ date: '2026-01-01T00:00:00Z', total_value: 10000 }],
      refetch,
    } as any);
    renderWithProviders(<PerformanceTab />);
    await waitFor(() => {
      expect(screen.getByLabelText('Performance chart')).toBeInTheDocument();
    });
  });

  it('shows loading state while history is pending', () => {
    mockUsePortfolio.usePortfolioPerformanceHistory.mockReturnValue({
      isPending: true,
      isError: false,
      isSuccess: false,
      data: undefined,
      refetch: vi.fn(),
    } as any);
    renderWithProviders(<PerformanceTab />);
    expect(screen.getByText(/Loading performance history/i)).toBeInTheDocument();
  });

  it('shows error with retry', async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    mockUsePortfolio.usePortfolioPerformanceHistory.mockReturnValue({
      isPending: false,
      isError: true,
      isSuccess: false,
      data: undefined,
      error: new Error('test'),
      refetch,
    } as any);
    renderWithProviders(<PerformanceTab />);
    expect(screen.getByText(/Failed to load performance history/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^retry$/i }));
    expect(refetch).toHaveBeenCalled();
  });

  it('shows empty state when history succeeds with no points', () => {
    mockUsePortfolio.usePortfolioPerformanceHistory.mockReturnValue({
      isPending: false,
      isError: false,
      isSuccess: true,
      data: [],
      refetch: vi.fn(),
    } as any);
    renderWithProviders(<PerformanceTab />);
    expect(screen.getByText(/No performance history yet/i)).toBeInTheDocument();
  });
});

describe('RiskTab', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('each failed section has its own retry control', async () => {
    const user = userEvent.setup();
    const refetchRisk = vi.fn();
    const refetchDiv = vi.fn();
    const refetchMargin = vi.fn();
    const refetchBal = vi.fn();
    mockUsePortfolio.usePortfolioAccounts.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as any);
    mockUsePortfolio.useRiskMetrics.mockReturnValue({
      isPending: false,
      isError: true,
      data: undefined,
      refetch: refetchRisk,
    } as any);
    mockUsePortfolio.useDividendSummary.mockReturnValue({
      isPending: false,
      isError: true,
      data: undefined,
      refetch: refetchDiv,
    } as any);
    mockUsePortfolio.useMarginInterest.mockReturnValue({
      isPending: false,
      isError: true,
      data: undefined,
      refetch: refetchMargin,
    } as any);
    mockUsePortfolio.useAccountBalances.mockReturnValue({
      isPending: false,
      isError: true,
      data: undefined,
      refetch: refetchBal,
    } as any);
    mockUsePortfolio.useLiveSummary.mockReturnValue({ data: null, isPending: false, isError: false, refetch: vi.fn() } as any);
    renderWithProviders(<RiskTab />);
    const retries = screen.getAllByRole('button', { name: /^retry$/i });
    expect(retries).toHaveLength(4);
    await user.click(retries[0]!);
    expect(refetchRisk).toHaveBeenCalled();
  });
});

describe('AllocationTab', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('shows loading skeleton', () => {
    mockUsePortfolioAllocation.mockReturnValue({
      isPending: true,
      isError: false,
      data: undefined,
      refetch: vi.fn(),
    } as any);
    renderWithProviders(<AllocationTab />);
    expect(document.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error with retry', async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    mockUsePortfolioAllocation.mockReturnValue({
      isPending: false,
      isError: true,
      data: undefined,
      refetch,
    } as any);
    renderWithProviders(<AllocationTab />);
    expect(screen.getByText(/Could not load allocation/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^retry$/i }));
    expect(refetch).toHaveBeenCalled();
  });

  it('shows empty when groups are empty', () => {
    mockUsePortfolioAllocation.mockReturnValue({
      isPending: false,
      isError: false,
      data: { groups: [], total_value: 0, group_by: 'sector', generated_at: '' },
      refetch: vi.fn(),
    } as any);
    renderWithProviders(<AllocationTab />);
    expect(screen.getByText(/Nothing to allocate yet/i)).toBeInTheDocument();
  });
});
