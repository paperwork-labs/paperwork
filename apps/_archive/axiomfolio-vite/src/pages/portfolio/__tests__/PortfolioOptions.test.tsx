import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { cleanup, screen } from '@testing-library/react';

import { renderWithProviders } from '@/test/render';

/* ------------------------------------------------------------------ */
/* Hoisted mocks                                                       */
/* ------------------------------------------------------------------ */

const mockUsePortfolio = vi.hoisted(() => ({
  useOptions: vi.fn(),
  usePortfolioSync: vi.fn(),
  usePortfolioAccounts: vi.fn(),
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

const mockApi = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('../../../services/api', () => ({
  default: mockApi,
  marketDataApi: { getHistory: vi.fn() },
}));

vi.mock('../../../hooks/usePortfolio', async () => {
  const actual = await vi.importActual<typeof import('../../../hooks/usePortfolio')>(
    '../../../hooks/usePortfolio',
  );
  return { ...actual, ...mockUsePortfolio };
});

vi.mock('../../../hooks/useAccountFilter', () => ({
  useAccountFilter: mockUseAccountFilterImpl,
}));

vi.mock('../../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({ currency: 'USD' as const, timezone: 'UTC' }),
}));

vi.mock('../../../context/AccountContext', () => ({
  useAccountContext: () => ({ selected: 'all', setSelected: vi.fn() }),
}));

vi.mock('../../../context/AuthContext', async () => {
  const actual = await vi.importActual<
    typeof import('../../../context/AuthContext')
  >('../../../context/AuthContext');
  return {
    ...actual,
    useAuth: () => ({ user: { id: 1, role: 'OWNER' } }),
    useAuthOptional: () => ({ user: { id: 1, role: 'OWNER' } }),
  };
});

vi.mock('../../../components/market/SymbolChartUI', () => ({
  ChartContext: { Provider: ({ children }: { children: React.ReactNode }) => <>{children}</> },
  SymbolLink: ({ symbol }: { symbol: string }) => <span>{symbol}</span>,
  ChartSlidePanel: () => null,
}));

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function setHappyPathDefaults(positions: any[], underlyings: Record<string, any> = {}) {
  mockUsePortfolio.useOptions.mockReturnValue({
    portfolio: {
      data: { data: { positions, underlyings } },
      isPending: false,
      error: null,
      refetch: vi.fn(),
    },
    summary: {
      data: { data: { summary: {} } },
      isPending: false,
      error: null,
      refetch: vi.fn(),
    },
    // `useOptions` unwraps ``portfolio.data.data`` into ``data`` for callers.
    data: { positions, underlyings },
    summaryData: { summary: {} },
    isPending: false,
    error: null,
  } as any);
  mockUsePortfolio.usePortfolioAccounts.mockReturnValue({
    data: [],
    isPending: false,
    error: null,
    refetch: vi.fn(),
  } as any);
  mockUsePortfolio.usePortfolioSync.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as any);
}

/* ------------------------------------------------------------------ */
/* Tests                                                               */
/* ------------------------------------------------------------------ */

describe('PortfolioOptions - broker-agnostic chain tab', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('never shows the "IB Gateway Required" copy (PR guard)', async () => {
    setHappyPathDefaults([]);
    mockApi.get.mockImplementation((url: string) => {
      if (url.includes('/portfolio/options/chain/sources')) {
        return Promise.resolve({
          data: {
            data: {
              sources: [
                {
                  name: 'ibkr_gateway',
                  label: 'IB Gateway',
                  available: false,
                  reason: 'no_ibkr_account',
                  kind: 'broker',
                },
                {
                  name: 'yfinance',
                  label: 'Yahoo Finance',
                  available: false,
                  reason: 'yfinance_not_installed',
                  kind: 'provider',
                },
              ],
              any_available: false,
            },
          },
        });
      }
      if (url.includes('/portfolio/options/gateway-status')) {
        return Promise.resolve({ data: { data: { connected: false } } });
      }
      return Promise.resolve({ data: { data: {} } });
    });

    const { default: PortfolioOptions } = await import('../PortfolioOptions');
    const { container } = renderWithProviders(<PortfolioOptions />);

    // Switch to chain tab.
    const chainBtn = screen.getByRole('button', { name: /option chain/i });
    chainBtn.click();

    await new Promise((r) => setTimeout(r, 60));

    expect(container.textContent).not.toMatch(/IB Gateway Required/i);
    expect(container.textContent).not.toMatch(/make ib-up/i);
  });

  it('shows broker-agnostic empty state with CTA when no chain source is available', async () => {
    setHappyPathDefaults([]);
    mockApi.get.mockImplementation((url: string) => {
      if (url.includes('/portfolio/options/chain/sources')) {
        return Promise.resolve({
          data: {
            data: {
              sources: [],
              any_available: false,
            },
          },
        });
      }
      if (url.includes('/portfolio/options/gateway-status')) {
        return Promise.resolve({ data: { data: { connected: false } } });
      }
      return Promise.resolve({ data: { data: {} } });
    });

    const { default: PortfolioOptions } = await import('../PortfolioOptions');
    renderWithProviders(<PortfolioOptions />);
    const chainBtn = screen.getByRole('button', { name: /option chain/i });
    chainBtn.click();

    await new Promise((r) => setTimeout(r, 60));

    expect(
      screen.getByText(/Option chain data isn't available right now/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /open connections/i }),
    ).toBeInTheDocument();
  });
});

describe('PortfolioOptions - multi-broker positions', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders broker badges for options from different brokers', async () => {
    const positions = [
      {
        id: 1,
        symbol: 'RDDT CALL 100 2026-01-16',
        underlying_symbol: 'RDDT',
        strike_price: 100,
        expiration_date: '2026-01-16',
        option_type: 'call',
        quantity: 1,
        market_value: 100,
        unrealized_pnl: 10,
        days_to_expiration: 30,
        broker: 'schwab',
        account_number: 'S-0001',
      },
      {
        id: 2,
        symbol: 'MSTR PUT 300 2026-01-16',
        underlying_symbol: 'MSTR',
        strike_price: 300,
        expiration_date: '2026-01-16',
        option_type: 'put',
        quantity: -1,
        market_value: 250,
        unrealized_pnl: -20,
        days_to_expiration: 30,
        broker: 'ibkr',
        account_number: 'U1234567',
      },
    ];
    setHappyPathDefaults(positions, {
      RDDT: { calls: [positions[0]], puts: [], total_value: 100, total_pnl: 10 },
      MSTR: { calls: [], puts: [positions[1]], total_value: 250, total_pnl: -20 },
    });
    mockUseAccountFilterImpl.mockReturnValue({
      selectedAccount: 'all' as const,
      setSelectedAccount: vi.fn(),
      filteredData: positions,
      accounts: [],
      totalValue: 350,
      totalPnL: -10,
      totalPositions: 2,
      isLoading: false,
      error: null,
    });
    mockApi.get.mockResolvedValue({ data: { data: { connected: false } } });

    const { default: PortfolioOptions } = await import('../PortfolioOptions');
    const { container } = renderWithProviders(<PortfolioOptions />);

    // Broker labels render somewhere on the positions tab.
    expect(container.textContent).toMatch(/Schwab/);
    expect(container.textContent).toMatch(/IBKR/);
  });
});
