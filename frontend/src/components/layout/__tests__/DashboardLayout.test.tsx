import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { screen, cleanup } from '@/test/testing-library';

import DashboardLayout from '../DashboardLayout';

// ---- mocks ----------------------------------------------------------------

let mockedAuth: {
  user: { username: string; role: string };
  logout: ReturnType<typeof vi.fn>;
  ready: boolean;
} = {
  user: { username: 'tester', role: 'user' },
  logout: vi.fn(),
  ready: true,
};

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => mockedAuth,
}));

let mockedBalances: {
  data: unknown[] | undefined;
  isPending: boolean;
  isError: boolean;
  isSuccess: boolean;
  refetch: ReturnType<typeof vi.fn>;
} = {
  data: [{ id: 1, broker: 'IBKR' }],
  isPending: false,
  isError: false,
  isSuccess: true,
  refetch: vi.fn(),
};

vi.mock('@/hooks/usePortfolio', () => ({
  useAccountBalances: () => mockedBalances,
}));

vi.mock('@/hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({ currency: 'USD' }),
}));

const mockedAccountContext = {
  accounts: [],
  loading: false,
  selected: 'all' as const,
  setSelected: vi.fn(),
};
vi.mock('../../../context/AccountContext', () => ({
  useAccountContext: () => mockedAccountContext,
}));

// SidebarStatusDot polls /admin/health — return nothing to keep tests pure.
vi.mock('../../../hooks/useAdminHealth', () => ({
  __esModule: true,
  default: () => ({ health: null, loading: false, isError: false, refresh: vi.fn() }),
}));

vi.mock('../../../services/api', () => ({
  portfolioApi: { getLive: vi.fn().mockResolvedValue({ data: { accounts: {} } }) },
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

describe('DashboardLayout tier chips + section structure', () => {
  beforeEach(() => {
    cleanup();
    mockDesktopViewport();
    localStorage.removeItem('qm.ui.sidebar_open');
    mockedAuth = {
      user: { username: 'tester', role: 'user' },
      logout: vi.fn(),
      ready: true,
    };
    mockedBalances = {
      data: [{ id: 1, broker: 'IBKR' }],
      isPending: false,
      isError: false,
      isSuccess: true,
      refetch: vi.fn(),
    };
  });

  it('renders the six canonical sections in order: TODAY / PORTFOLIO / SIGNALS / MARKETS / LAB / SETTINGS', () => {
    const { container } = renderWithProviders(<DashboardLayout />);
    const sections = Array.from(
      container.querySelectorAll<HTMLElement>('[data-section-id]'),
    ).map((el) => el.getAttribute('data-section-id'));
    expect(sections).toEqual([
      'today',
      'portfolio',
      'signals',
      'markets',
      'lab',
      'settings',
    ]);
  });

  it('renders Pro chip on SIGNALS and MARKETS sections for every user', () => {
    renderWithProviders(<DashboardLayout />);
    // Two Pro chips (Signals + Markets), one Pro+ chip (Lab).
    const proChips = document.querySelectorAll('[data-tier-chip="pro"]');
    const proPlusChips = document.querySelectorAll('[data-tier-chip="pro_plus"]');
    expect(proChips.length).toBe(2);
    expect(proPlusChips.length).toBe(1);
  });

  it('never renders a tier chip on the free sections (TODAY / PORTFOLIO / SETTINGS)', () => {
    const { container } = renderWithProviders(<DashboardLayout />);
    const freeSections = ['today', 'portfolio', 'settings'];
    for (const id of freeSections) {
      const section = container.querySelector<HTMLElement>(`[data-section-id="${id}"]`);
      expect(section).not.toBeNull();
      expect(section!.querySelector('[data-tier-chip]')).toBeNull();
    }
  });

  it('renders the collapsed Portfolio hub (4 items) rather than the legacy 11-item list', () => {
    const { container } = renderWithProviders(<DashboardLayout />);
    const section = container.querySelector<HTMLElement>('[data-section-id="portfolio"]');
    const items = section?.querySelectorAll('[data-nav-path]') ?? [];
    expect(items.length).toBe(4);
    const paths = Array.from(items).map((el) => el.getAttribute('data-nav-path'));
    expect(paths).toEqual([
      '/portfolio',
      '/portfolio/positions',
      '/portfolio/activity',
      '/market/workspace',
    ]);
  });

  it('points the Markets hub at /market/universe (merged Watchlist + Lookup)', () => {
    const { container } = renderWithProviders(<DashboardLayout />);
    const section = container.querySelector<HTMLElement>('[data-section-id="markets"]');
    const universe = section?.querySelector<HTMLElement>('[data-nav-path="/market/universe"]');
    expect(universe).not.toBeNull();
    // Old Watchlist / Symbol lookup entries must be gone from the sidebar.
    expect(section?.querySelector('[data-nav-path="/market/tracked"]')).toBeNull();
    expect(section?.querySelector('[data-nav-path="/market/scanner"]')).toBeNull();
  });

  it('never renders a standalone Connections nav entry (moved to Settings)', () => {
    const { container } = renderWithProviders(<DashboardLayout />);
    const portfolio = container.querySelector<HTMLElement>('[data-section-id="portfolio"]');
    expect(portfolio?.querySelector('[data-nav-path="/settings/connections"]')).toBeNull();
  });

  it('never renders Stage Scan in the sidebar (absorbed as a Candidates preset)', () => {
    const { container } = renderWithProviders(<DashboardLayout />);
    expect(container.querySelector('[data-nav-path="/signals/stage-scan"]')).toBeNull();
  });

  it('hides PORTFOLIO for a free user with no brokers', () => {
    mockedBalances = { ...mockedBalances, data: [] };
    const { container } = renderWithProviders(<DashboardLayout />);
    expect(container.querySelector('[data-section-id="portfolio"]')).toBeNull();
    // Tier chips remain visible — Pro/Pro+ sections are not gated by broker presence.
    expect(container.querySelector('[data-section-id="signals"]')).not.toBeNull();
  });
});
