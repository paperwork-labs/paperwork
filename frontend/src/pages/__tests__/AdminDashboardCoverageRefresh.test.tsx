import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import AdminDashboard from '../../pages/AdminDashboard';
import { renderWithProviders } from '../../test/render';

const apiPost = vi.fn().mockResolvedValue({ data: { task_id: 'task-123' } });
const apiGet = vi.fn().mockResolvedValue({ data: {} });

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    currency: 'USD',
    timezone: 'UTC',
    tableDensity: 'comfortable',
    coverageHistogramWindowDays: 50,
  }),
}));

vi.mock('../../services/api', () => {
  return {
    default: {
      post: (...args: any[]) => apiPost(...args),
      get: (...args: any[]) => apiGet(...args),
    },
  };
});

vi.mock('react-hot-toast', () => {
  return {
    default: {
      success: vi.fn(),
      error: vi.fn(),
    },
  };
});

vi.mock('../../hooks/useCoverageSnapshot', () => {
  return {
    default: () => ({
      snapshot: {
        meta: {
          source: 'db',
          snapshot_age_seconds: 9999,
          updated_at: '2026-01-07T08:50:30.000Z',
          backfill_5m_enabled: true,
        },
        status: { label: 'degraded', summary: 'test', daily_pct: 0, m5_pct: 0, stale_daily: 1, stale_m5: 0 },
        symbols: 3,
        daily: {
          last: {
            A: '2026-01-08T00:00:00Z',
            B: '2026-01-08T00:00:00Z',
            C: '2026-01-02T00:00:00Z',
          },
          fill_by_date: [
            { date: '2026-01-08', symbol_count: 2, pct_of_universe: 66.7 },
            { date: '2026-01-02', symbol_count: 1, pct_of_universe: 33.3 },
          ],
          snapshot_fill_by_date: [
            { date: '2026-01-08', symbol_count: 2, pct_of_universe: 66.7 },
          ],
        },
      },
      refresh: vi.fn(),
      sparkline: { daily_pct: [], m5_pct: [], labels: [] },
      kpis: [],
      actions: [],
      hero: { buckets: [], statusLabel: 'DEGRADED', statusColor: 'red', summary: 'test', updatedDisplay: '—', updatedRelative: '—', isSnapshotStale: false, staleCounts: { daily: 1, m5: 0 }, trackedCount: 0, totalSymbols: 0, historySamples: 0 },
      loading: false,
    }),
  };
});

vi.mock('../../components/coverage/CoverageSummaryCard', () => {
  return {
    CoverageSummaryCard: ({ children }: any) => <div>{children}</div>,
    CoverageKpiGrid: () => <div />,
    CoverageTrendGrid: () => <div />,
    CoverageBucketsGrid: () => <div />,
  };
});

describe('AdminDashboard coverage refresh', () => {
  beforeEach(() => {
    apiPost.mockClear();
    apiGet.mockClear();
  });

  it('auto-triggers coverage refresh when snapshot is stale/missing cache', async () => {
    renderWithProviders(<AdminDashboard />, { route: '/settings/admin/dashboard' });
    // Auto-refresh effect should queue a refresh
    expect(apiPost).toHaveBeenCalledWith('/market-data/admin/coverage/refresh');
  });

  it('allows manual refresh via button', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminDashboard />, { route: '/settings/admin/dashboard' });
    const btn = (await screen.findAllByRole('button', { name: /refresh coverage/i }))[0];
    await user.click(btn);
    expect(apiPost).toHaveBeenCalledWith('/market-data/admin/coverage/refresh');
    expect(apiPost.mock.calls.filter((c) => c[0] === '/market-data/admin/coverage/refresh').length).toBeGreaterThanOrEqual(2);
  });

  it('renders guided actions', async () => {
    renderWithProviders(<AdminDashboard />, { route: '/settings/admin/dashboard' });
    const restore = await screen.findAllByRole('button', { name: /Restore Daily Coverage \(Tracked\)/i });
    expect(restore.length).toBeGreaterThanOrEqual(1);
    const stale = await screen.findAllByRole('button', { name: /Backfill Daily \(Stale Only\)/i });
    expect(stale.length).toBeGreaterThanOrEqual(1);
  });

  it('exposes period backfill controls in Advanced', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminDashboard />, { route: '/settings/admin/dashboard' });
    const toggles = await screen.findAllByRole('button', { name: /show advanced/i });
    await user.click(toggles[0]);
    const btn = await screen.findByRole('button', { name: /Backfill Daily Bars \(period\)/i });
    await user.click(btn);
    expect(apiPost).toHaveBeenCalledWith('/market-data/admin/backfill/daily?days=252');
  });

  it('renders daily fill-by-date distribution', async () => {
    renderWithProviders(<AdminDashboard />, { route: '/settings/admin/dashboard' });
    const blocks = await screen.findAllByText(/Daily fill by date/i);
    expect(blocks.length).toBeGreaterThanOrEqual(1);
    const newest = await screen.findAllByText(/Newest date: 2026-01-08/i);
    expect(newest.length).toBeGreaterThanOrEqual(1);
    // Tooltip-only details: ensure hint is present.
    expect(document.body.textContent || '').toContain('Hover a bar to see date');
  });
});


