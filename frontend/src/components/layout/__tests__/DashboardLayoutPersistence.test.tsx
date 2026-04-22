import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { screen } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';

import DashboardLayout from '../DashboardLayout';

// Mock Auth + Account context dependencies.
let mockedAuth: {
  user: { username: string; role: string };
  logout: ReturnType<typeof vi.fn>;
  ready: boolean;
} = {
  user: { username: 'tester', role: 'user' },
  logout: vi.fn(),
  ready: true,
};

let mockedBalances: {
  data: unknown[] | undefined;
  isPending: boolean;
  isError: boolean;
  isSuccess: boolean;
  refetch: ReturnType<typeof vi.fn>;
} = {
  data: [],
  isPending: false,
  isError: false,
  isSuccess: true,
  refetch: vi.fn(),
};

vi.mock('../../../context/AuthContext', () => {
  return {
    useAuth: () => mockedAuth,
  };
});

vi.mock('@/hooks/usePortfolio', () => ({
  useAccountBalances: () => mockedBalances,
}));

// TopBarAccountSelector reads currency from this hook; the real
// implementation reaches into AuthContext which the test stubs out below.
vi.mock('@/hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({ currency: 'USD' }),
}));

let mockedAccountContext = {
  accounts: [] as Array<{ account_number: string; account_name?: string }>,
  loading: false,
  selected: 'all' as const,
  setSelected: vi.fn(),
};
vi.mock('../../../context/AccountContext', () => ({
  useAccountContext: () => mockedAccountContext,
}));

function mockDesktopViewport(): void {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

// Avoid network calls made on mount.
vi.mock('../../../services/api', () => {
  return {
    portfolioApi: {
      getLive: vi.fn().mockResolvedValue({ data: { accounts: {} } }),
    },
  };
});

describe('DashboardLayout sidebar persistence', () => {
  beforeEach(() => {
    mockDesktopViewport();
    localStorage.removeItem('qm.ui.sidebar_open');
    mockedAuth = {
      user: { username: 'tester', role: 'user' },
      logout: vi.fn(),
      ready: true,
    };
    mockedBalances = {
      data: [],
      isPending: false,
      isError: false,
      isSuccess: true,
      refetch: vi.fn(),
    };
  });

  it('reads collapsed state from localStorage and persists on toggle', async () => {
    const user = userEvent.setup();
    localStorage.setItem('qm.ui.sidebar_open', '0');

    renderWithProviders(<DashboardLayout />);

    // In collapsed desktop mode, brand moves to header-left.
    expect(screen.getAllByText('AxiomFolio').length).toBeGreaterThan(0);

    await user.click(screen.getByRole('button', { name: /expand or collapse sidebar/i }));

    expect(localStorage.getItem('qm.ui.sidebar_open')).toBe('1');
  });

  it('hides portfolio section for non-admin users with no broker accounts', () => {
    renderWithProviders(<DashboardLayout />);
    expect(screen.getAllByText('TODAY').length).toBeGreaterThan(0);
    expect(screen.getByText('Watchlist')).toBeInTheDocument();
    expect(screen.queryByText('PORTFOLIO')).toBeNull();
    expect(screen.queryByText('Agent Guru')).toBeNull();
    expect(screen.queryByText('Overview')).toBeNull();
    expect(screen.queryByRole('button', { name: /account filter/i })).toBeNull();
  });

  it('shows portfolio and Strategies under LAB when user has broker balances', () => {
    mockedBalances = {
      data: [{ id: 1, broker: 'IBKR' }],
      isPending: false,
      isError: false,
      isSuccess: true,
      refetch: vi.fn(),
    };
    mockedAccountContext = {
      accounts: [{ account_number: 'U123', account_name: 'Test Account' }],
      loading: false,
      selected: 'all',
      setSelected: vi.fn(),
    };
    renderWithProviders(<DashboardLayout />);
    expect(screen.getByText('PORTFOLIO')).toBeInTheDocument();
    expect(screen.getByText('LAB')).toBeInTheDocument();
    expect(screen.queryByText('STRATEGY')).toBeNull();
    expect(screen.getByText('Workspace')).toBeInTheDocument();
    expect(screen.getAllByText('Strategies').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.queryByText('Agent Guru')).toBeNull();
    expect(screen.getByRole('button', { name: /account filter/i })).toBeInTheDocument();
  });

  it('does not keep portfolio dashboard active on portfolio categories route', () => {
    mockedBalances = {
      data: [{ id: 1, broker: 'IBKR' }],
      isPending: false,
      isError: false,
      isSuccess: true,
      refetch: vi.fn(),
    };
    const { container } = renderWithProviders(<DashboardLayout />, { route: '/portfolio/categories' });
    const portfolioOverview = container.querySelector('[data-nav-path="/portfolio"]');
    const portfolioCategories = container.querySelector('[data-nav-path="/portfolio/categories"]');
    expect(portfolioOverview?.getAttribute('data-active')).toBe('false');
    expect(portfolioCategories?.getAttribute('data-active')).toBe('true');
  });

  it('highlights Strategies nav on strategy detail route', () => {
    mockedBalances = {
      data: [{ id: 1, broker: 'IBKR' }],
      isPending: false,
      isError: false,
      isSuccess: true,
      refetch: vi.fn(),
    };
    const { container } = renderWithProviders(<DashboardLayout />, {
      route: '/lab/strategies/strat-1',
    });
    const strategies = container.querySelector('[data-nav-path="/lab/strategies"]');
    expect(strategies?.getAttribute('data-active')).toBe('true');
  });
});


