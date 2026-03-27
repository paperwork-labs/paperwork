import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { screen } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';

import DashboardLayout from '../DashboardLayout';

// Mock Auth + Account context dependencies.
let mockedAuth: any = {
  user: { username: 'tester', role: 'user' },
  logout: vi.fn(),
  appSettings: { market_only_mode: true, portfolio_enabled: false, strategy_enabled: false },
  appSettingsReady: true,
  ready: true,
};

vi.mock('../../../context/AuthContext', () => {
  return {
    useAuth: () => mockedAuth,
  };
});

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
      appSettings: { market_only_mode: true, portfolio_enabled: false, strategy_enabled: false },
      appSettingsReady: true,
      ready: true,
    };
  });

  it('reads collapsed state from localStorage and persists on toggle', async () => {
    const user = userEvent.setup();
    localStorage.setItem('qm.ui.sidebar_open', '0');

    renderWithProviders(<DashboardLayout />);

    // In collapsed desktop mode, brand moves to header-left.
    expect(screen.getAllByText('AxiomFolio').length).toBeGreaterThan(0);

    await user.click(screen.getByRole('button', { name: /menu/i }));

    expect(localStorage.getItem('qm.ui.sidebar_open')).toBe('1');
  });

  it('hides portfolio and strategy sections for non-admin market-only defaults', () => {
    renderWithProviders(<DashboardLayout />);
    expect(screen.getAllByText('MARKET').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Tracked').length).toBeGreaterThan(0);
    expect(screen.queryByText('PORTFOLIO')).toBeNull();
    expect(screen.queryByText('Agent Guru')).toBeNull();
    expect(screen.queryByText('Overview')).toBeNull();
    expect(screen.queryByRole('button', { name: /account filter/i })).toBeNull();
  });

  it('shows portfolio and Strategies under MARKET when section flags are enabled', () => {
    mockedAuth = {
      user: { username: 'tester', role: 'user' },
      logout: vi.fn(),
      appSettings: { market_only_mode: false, portfolio_enabled: true, strategy_enabled: true },
      appSettingsReady: true,
      ready: true,
    };
    mockedAccountContext = {
      accounts: [{ account_number: 'U123', account_name: 'Test Account' }],
      loading: false,
      selected: 'all',
      setSelected: vi.fn(),
    };
    renderWithProviders(<DashboardLayout />);
    expect(screen.getByText('PORTFOLIO')).toBeInTheDocument();
    expect(screen.queryByText('STRATEGY')).toBeNull();
    expect(screen.getByText('Workspace')).toBeInTheDocument();
    expect(screen.getByText('Strategies')).toBeInTheDocument();
    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.queryByText('Agent Guru')).toBeNull();
    expect(screen.getByRole('button', { name: /account filter/i })).toBeInTheDocument();
  });

  it('does not keep portfolio dashboard active on portfolio categories route', () => {
    mockedAuth = {
      user: { username: 'tester', role: 'user' },
      logout: vi.fn(),
      appSettings: { market_only_mode: false, portfolio_enabled: true, strategy_enabled: true },
      appSettingsReady: true,
      ready: true,
    };
    const { container } = renderWithProviders(<DashboardLayout />, { route: '/portfolio/categories' });
    const portfolioOverview = container.querySelector('[data-nav-path="/portfolio"]');
    const portfolioCategories = container.querySelector('[data-nav-path="/portfolio/categories"]');
    expect(portfolioOverview?.getAttribute('data-active')).toBe('false');
    expect(portfolioCategories?.getAttribute('data-active')).toBe('true');
  });

  it('highlights Strategies nav on strategy detail route', () => {
    mockedAuth = {
      user: { username: 'tester', role: 'user' },
      logout: vi.fn(),
      appSettings: { market_only_mode: false, portfolio_enabled: true, strategy_enabled: true },
      appSettingsReady: true,
      ready: true,
    };
    const { container } = renderWithProviders(<DashboardLayout />, {
      route: '/market/strategies/strat-1',
    });
    const strategies = container.querySelector('[data-nav-path="/market/strategies"]');
    expect(strategies?.getAttribute('data-active')).toBe('true');
  });

  it('shows Agent Guru in MARKET for admin users', () => {
    mockedAuth = {
      user: { username: 'admin', role: 'admin' },
      logout: vi.fn(),
      appSettings: { market_only_mode: true, portfolio_enabled: false, strategy_enabled: false },
      appSettingsReady: true,
      ready: true,
    };
    const { container } = renderWithProviders(<DashboardLayout />);
    expect(container.querySelectorAll('[data-nav-path="/admin/agent"]').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SETTINGS').length).toBeGreaterThan(0);
  });
});


