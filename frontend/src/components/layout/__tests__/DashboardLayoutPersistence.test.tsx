import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { screen } from '@testing-library/react';
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

vi.mock('../../../context/AccountContext', () => {
  return {
    useAccountContext: () => ({
      accounts: [],
      loading: false,
      selected: 'all',
      setSelected: vi.fn(),
    }),
  };
});

// Ensure desktop path so sidebar exists.
vi.mock('@chakra-ui/react', async () => {
  const actual: any = await vi.importActual('@chakra-ui/react');
  return {
    ...actual,
    useMediaQuery: () => [true],
  };
});

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

    // When collapsed, brand text should be hidden.
    expect(screen.queryByText('AxiomFolio')).toBeNull();

    await user.click(screen.getByRole('button', { name: /menu/i }));

    expect(localStorage.getItem('qm.ui.sidebar_open')).toBe('1');
  });

  it('hides portfolio and strategy sections for non-admin market-only defaults', () => {
    renderWithProviders(<DashboardLayout />);
    expect(screen.getAllByText('MARKET').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Tracked').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Coverage').length).toBeGreaterThan(0);
    expect(screen.queryByText('PORTFOLIO')).toBeNull();
    expect(screen.queryByText('STRATEGY')).toBeNull();
  });

  it('shows portfolio and strategy sections when section flags are enabled', () => {
    mockedAuth = {
      user: { username: 'tester', role: 'user' },
      logout: vi.fn(),
      appSettings: { market_only_mode: false, portfolio_enabled: true, strategy_enabled: true },
      appSettingsReady: true,
      ready: true,
    };
    renderWithProviders(<DashboardLayout />);
    expect(screen.getByText('PORTFOLIO')).toBeInTheDocument();
    expect(screen.getByText('STRATEGY')).toBeInTheDocument();
    expect(screen.getByText('Workspace')).toBeInTheDocument();
    expect(screen.getByText('Strategies')).toBeInTheDocument();
  });

  it('does not keep portfolio dashboard active on portfolio categories route', () => {
    mockedAuth = {
      user: { username: 'tester', role: 'user' },
      logout: vi.fn(),
      appSettings: { market_only_mode: false, portfolio_enabled: true, strategy_enabled: true },
      appSettingsReady: true,
      ready: true,
    };
    const { container } = renderWithProviders(<DashboardLayout />, { route: '/portfolio-categories' });
    const portfolioDashboard = container.querySelector('[data-nav-path="/portfolio"]');
    const portfolioCategories = container.querySelector('[data-nav-path="/portfolio-categories"]');
    expect(portfolioDashboard?.getAttribute('data-active')).toBe('false');
    expect(portfolioCategories?.getAttribute('data-active')).toBe('true');
  });

  it('does not keep strategies active on strategy manager route', () => {
    mockedAuth = {
      user: { username: 'tester', role: 'user' },
      logout: vi.fn(),
      appSettings: { market_only_mode: false, portfolio_enabled: true, strategy_enabled: true },
      appSettingsReady: true,
      ready: true,
    };
    const { container } = renderWithProviders(<DashboardLayout />, { route: '/strategies-manager' });
    const strategyManager = container.querySelector('[data-nav-path="/strategies-manager"]');
    const strategies = container.querySelector('[data-nav-path="/strategies"]');
    expect(strategyManager?.getAttribute('data-active')).toBe('true');
    expect(strategies?.getAttribute('data-active')).toBe('false');
  });
});


