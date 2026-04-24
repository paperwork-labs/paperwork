import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { act, cleanup, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { renderWithProviders } from '@/test/render';

/**
 * G5 -- IV column rendering (R-IV01 guard).
 *
 * These tests pin the four observable states of the IV cell in the
 * options positions table:
 *
 *  1. loading  -- before `useOptions` resolves, the positions area
 *                 renders a skeleton (no `0%` / `$0.00`).
 *  2. absent   -- `implied_volatility` is `null` / `undefined` / NaN ->
 *                 render `—` with an accessible tooltip (aria-label +
 *                 title). This is *how we distinguish* absent from 0.
 *  3. numeric  -- `implied_volatility = 0.25` -> render `25%`.
 *  4. zero     -- `implied_volatility = 0` renders as `0%` (a real
 *                 observation, not a silent fallback).
 *
 * We never want `?? 0` to creep back in -- a missing reading must be
 * visibly distinct from a zero reading at the component level.
 */

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
  const actual = await vi.importActual<typeof import('../../../context/AuthContext')>(
    '../../../context/AuthContext',
  );
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

type Pos = {
  id: number;
  symbol: string;
  underlying_symbol: string;
  strike_price: number;
  expiration_date: string;
  option_type: 'call' | 'put';
  quantity: number;
  market_value: number;
  unrealized_pnl: number;
  days_to_expiration: number;
  broker: string;
  account_number: string;
  implied_volatility?: number | null;
};

function pos(id: number, iv: number | null | undefined): Pos {
  return {
    id,
    symbol: `SYM${id} CALL 100 2026-01-16`,
    underlying_symbol: `SYM${id}`,
    strike_price: 100,
    expiration_date: '2026-01-16',
    option_type: 'call',
    quantity: 1,
    market_value: 100,
    unrealized_pnl: 10,
    days_to_expiration: 30,
    broker: 'ibkr',
    account_number: 'U1234567',
    implied_volatility: iv,
  };
}

function setPositions(positions: Pos[], opts: { loading?: boolean } = {}) {
  const isLoading = Boolean(opts.loading);
  mockUsePortfolio.useOptions.mockReturnValue({
    portfolio: {
      data: isLoading ? undefined : { data: { positions, underlyings: {} } },
      isPending: isLoading,
      error: null,
      refetch: vi.fn(),
    },
    summary: {
      data: isLoading ? undefined : { data: { summary: {} } },
      isPending: isLoading,
      error: null,
      refetch: vi.fn(),
    },
    data: isLoading ? undefined : { positions, underlyings: {} },
    summaryData: isLoading ? undefined : { summary: {} },
    isPending: isLoading,
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
  mockUseAccountFilterImpl.mockReturnValue({
    selectedAccount: 'all' as const,
    setSelectedAccount: vi.fn(),
    filteredData: positions,
    accounts: [],
    totalValue: positions.reduce((s, p) => s + p.market_value, 0),
    totalPnL: positions.reduce((s, p) => s + p.unrealized_pnl, 0),
    totalPositions: positions.length,
    isLoading,
    error: null,
  });
  mockApi.get.mockResolvedValue({ data: { data: { connected: false } } });
}

describe('PortfolioOptions - IV column (G5 R-IV01)', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  async function mountAndSwitchToTable() {
    const { default: PortfolioOptions } = await import('../PortfolioOptions');
    const rendered = renderWithProviders(<PortfolioOptions />);
    // Let the page settle: query cache, account filter, positions hook.
    await new Promise((r) => setTimeout(r, 60));
    // The IV cell lives in the positions table view; flip from the
    // default card layout to table so the <SortableTable> renders.
    const tableBtn = screen.getByRole('button', { name: /table view/i });
    await act(async () => {
      await userEvent.click(tableBtn);
    });
    await new Promise((r) => setTimeout(r, 30));
    return rendered;
  }

  it('renders "—" with unavailable tooltip when implied_volatility is null', async () => {
    setPositions([pos(1, null)]);
    const { container } = await mountAndSwitchToTable();
    // The R-IV01 guarantee is an aria-label distinguishing absent IV
    // from any numeric value. We query it directly to avoid matching
    // the `—` glyphs produced by unrelated columns (theta, delta, etc).
    const absentCells = container.querySelectorAll(
      '[aria-label="Implied volatility unavailable"]',
    );
    expect(absentCells.length).toBeGreaterThan(0);
    expect(absentCells[0]?.textContent).toBe('—');
  });

  it('renders unavailable tooltip when implied_volatility is undefined', async () => {
    setPositions([pos(2, undefined)]);
    const { container } = await mountAndSwitchToTable();
    const absentCells = container.querySelectorAll(
      '[aria-label="Implied volatility unavailable"]',
    );
    expect(absentCells.length).toBeGreaterThan(0);
    expect(absentCells[0]?.getAttribute('title')).toMatch(
      /IV unavailable from provider/i,
    );
  });

  it('renders a formatted percent when implied_volatility is a real number', async () => {
    setPositions([pos(3, 0.25)]);
    const { container } = await mountAndSwitchToTable();
    expect(container.textContent).toContain('25%');
  });

  it('renders a real 0% when IV actually is 0 (distinguish from missing)', async () => {
    setPositions([pos(4, 0)]);
    const { container } = await mountAndSwitchToTable();
    // Zero is a valid observation; absent IV renders as "—" (see the
    // null / undefined tests above). The two states stay visibly
    // distinct -- the silent-zero rule forbids *coercing* absent -> 0,
    // not reporting a true zero.
    expect(container.textContent).toMatch(/0%/);
  });

  it('does not render "0%" or "$0.00" while positions are loading', async () => {
    setPositions([], { loading: true });
    const { default: PortfolioOptions } = await import('../PortfolioOptions');
    const { container } = renderWithProviders(<PortfolioOptions />);
    await new Promise((r) => setTimeout(r, 60));
    // Loading state renders skeleton content, not a fake zero. The
    // card layout is default so we don't need to switch to table here.
    expect(container.textContent).not.toMatch(/(^|[^0-9])0%(?![0-9])/);
    expect(container.textContent).not.toMatch(/\$0\.00/);
  });
});
