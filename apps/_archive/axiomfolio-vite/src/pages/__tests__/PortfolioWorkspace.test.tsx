import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';

import { renderWithProviders } from '../../test/render';

// The workspace page mounts charts, the order manager, RS ribbons, and a
// dozen hooks. None of that is relevant to the tax-lots card we want to
// exercise here — stub the lot to keep the test deterministic and fast.

vi.mock('../../components/charts/SymbolChartWithMarkers', () => ({
  __esModule: true,
  default: () => <div data-testid="symbol-chart" />,
  getStoredIndicators: () => ({
    trendLines: false,
    gaps: false,
    tdSequential: false,
    emas: false,
    stage: false,
    supportResistance: false,
    rsMansfieldRibbon: false,
  }),
  storeIndicators: vi.fn(),
}));
vi.mock('../../components/charts/TradingViewChart', () => ({
  __esModule: true,
  default: () => <div data-testid="tv-chart" />,
}));
vi.mock('../../components/charts/RSMansfieldRibbon', () => ({
  RSMansfieldRibbon: () => null,
}));
vi.mock('../../components/charts/OliverKellBadges', () => ({
  OliverKellLegend: () => null,
}));
vi.mock('../../components/charts/TradeSegments', () => ({
  buildTradeSegmentsFromActivity: () => [],
}));
vi.mock('../../components/orders/TradeModal', () => ({
  __esModule: true,
  default: () => null,
}));
vi.mock('@/components/billing/TierGate', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockHoldings = [
  {
    id: 42,
    symbol: 'AAPL',
    shares: 10,
    market_value: 1850,
    average_cost: 150,
    cost_basis: 1500,
    unrealized_pnl: 350,
    unrealized_pnl_pct: 23.3,
    current_price: 185,
  },
];

vi.mock('../../hooks/usePortfolio', () => ({
  usePositions: () => ({ data: mockHoldings, isPending: false }),
  useActivity: () => ({ data: { activity: [] }, isPending: false }),
  useClosedPositions: () => ({ data: [], isPending: false }),
}));

vi.mock('../../hooks/useEntitlement', () => ({
  __esModule: true,
  default: () => ({ can: () => false, isLoading: false, isError: false }),
}));

vi.mock('../../hooks/useRSMansfield', () => ({
  useRSMansfield: () => ({ isPending: false, isError: false, error: null, points: [], refetch: vi.fn() }),
}));

vi.mock('../../context/AccountContext', () => ({
  useAccountContext: () => ({ selected: 'all' }),
}));

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({ currency: 'USD', timezone: 'UTC' }),
}));

vi.mock('../../hooks/useChartColors', () => ({
  useChartColors: () => ({}),
}));

const getHoldingTaxLotsMock = vi.fn();
const getHistoryMock = vi.fn().mockResolvedValue({ bars: [] });
const getSnapshotMock = vi.fn().mockResolvedValue({ data: null });
const getIndicatorSeriesMock = vi.fn().mockResolvedValue({ data: { volume_events: [], kell_patterns: [] } });

vi.mock('../../services/api', () => ({
  __esModule: true,
  default: { get: vi.fn().mockResolvedValue({ data: [] }) },
  marketDataApi: {
    getHistory: (...args: unknown[]) => getHistoryMock(...args),
    getSnapshot: (...args: unknown[]) => getSnapshotMock(...args),
    getIndicatorSeries: (...args: unknown[]) => getIndicatorSeriesMock(...args),
  },
  portfolioApi: {
    getHoldingTaxLots: (...args: unknown[]) => getHoldingTaxLotsMock(...args),
    createManualTaxLot: vi.fn(),
    updateManualTaxLot: vi.fn(),
    deleteManualTaxLot: vi.fn(),
  },
  unwrapResponse: (res: unknown, key: string) => {
    const r = res as Record<string, any> | undefined;
    return (r?.data?.data?.[key] ?? r?.data?.[key] ?? r?.[key] ?? []) as unknown[];
  },
}));

// Import AFTER mocks are registered so the module graph picks them up.
import PortfolioWorkspace from '../PortfolioWorkspace';

describe('PortfolioWorkspace tax-lots card', () => {
  beforeEach(() => {
    getHoldingTaxLotsMock.mockReset();
    getHistoryMock.mockClear();
    getSnapshotMock.mockClear();
  });
  afterEach(() => cleanup());

  it('renders the empty state with an "Add a lot" affordance when no lots exist', async () => {
    getHoldingTaxLotsMock.mockResolvedValueOnce({ tax_lots: [] });

    renderWithProviders(<PortfolioWorkspace />, { route: '/market/workspace' });

    await waitFor(() => {
      expect(screen.getByTestId('workspace-tax-lots-empty')).toBeInTheDocument();
    });
    expect(screen.getByText(/No lots tracked for AAPL/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Add a lot/i })).toBeInTheDocument();
    expect(screen.getByText(/Tax Lots for AAPL/i)).toBeInTheDocument();
  });

  it('renders the error state with a Retry button when the lots query fails', async () => {
    getHoldingTaxLotsMock.mockRejectedValueOnce(new Error('boom'));

    renderWithProviders(<PortfolioWorkspace />, { route: '/market/workspace' });

    await waitFor(() => {
      expect(screen.getByTestId('workspace-tax-lots-error')).toBeInTheDocument();
    });
    expect(screen.getByText(/Couldn't load lots for AAPL/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
  });

  it('renders the lot table when tax lots are present', async () => {
    getHoldingTaxLotsMock.mockResolvedValueOnce({
      tax_lots: [
        {
          id: 1,
          purchase_date: '2024-05-01',
          shares: 10,
          shares_remaining: 10,
          cost_per_share: 150,
          days_held: 400,
          is_long_term: true,
          source: 'OFFICIAL_STATEMENT',
        },
      ],
    });

    renderWithProviders(<PortfolioWorkspace />, { route: '/market/workspace' });

    await waitFor(() => {
      expect(screen.getByTestId('workspace-tax-lots-table')).toBeInTheDocument();
    });
    expect(screen.getByText(/Tax Lots for AAPL/i)).toBeInTheDocument();
  });

  it('flips to the add-lot form when "Add a lot" is clicked from the empty state', async () => {
    getHoldingTaxLotsMock.mockResolvedValueOnce({ tax_lots: [] });
    const user = userEvent.setup();

    renderWithProviders(<PortfolioWorkspace />, { route: '/market/workspace' });

    await waitFor(() => screen.getByTestId('workspace-tax-lots-empty'));
    await user.click(screen.getByRole('button', { name: /Add a lot/i }));
    expect(await screen.findByText(/Add Manual Lot/i)).toBeInTheDocument();
  });
});
