import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor, cleanup } from '@testing-library/react';
import AdminSchedules from '../../pages/AdminSchedules';
import { renderWithProviders } from '../../test/render';

afterEach(() => cleanup());

const MOCK_SCHEDULES = {
  schedules: [
    {
      id: 'admin_coverage_refresh',
      display_name: 'Coverage Health Check',
      group: 'market_data',
      task: 'backend.tasks.market_data_tasks.monitor_coverage_health',
      description: 'Measure data freshness and flag stale symbols',
      cron: '0 * * * *',
      timezone: 'UTC',
      enabled: true,
      render_service_id: 'srv-abc123',
      render_synced_at: '2026-02-17T09:00:00Z',
      render_sync_error: null,
      last_run: { task_name: 'admin_coverage_refresh', status: 'ok', started_at: '2026-02-17T09:00:00Z' },
    },
    {
      id: 'admin_coverage_backfill',
      display_name: 'Nightly Coverage Pipeline',
      group: 'market_data',
      task: 'backend.tasks.market_data_tasks.bootstrap_daily_coverage_tracked',
      description: 'Full nightly chain: constituents, tracked, daily bars, indicators',
      cron: '0 3 * * *',
      timezone: 'UTC',
      enabled: false,
      render_service_id: null,
      render_synced_at: null,
      render_sync_error: 'create_failed at 2026-02-17',
      last_run: null,
    },
    {
      id: 'admin_retention_enforce',
      display_name: 'Data Retention Cleanup',
      group: 'maintenance',
      task: 'backend.tasks.market_data_tasks.enforce_price_data_retention',
      description: 'Purge 5-minute bars older than the configured retention window',
      cron: '30 4 * * *',
      timezone: 'UTC',
      enabled: true,
      render_service_id: null,
      render_synced_at: null,
      render_sync_error: null,
      last_run: null,
    },
  ],
  mode: 'db',
  render_sync_enabled: true,
};

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    currency: 'USD',
    timezone: 'America/Los_Angeles',
    tableDensity: 'comfortable',
  }),
}));

const MOCK_HISTORY = {
  history: [
    {
      id: 1,
      schedule_id: 'admin_coverage_refresh',
      action: 'created',
      actor: 'admin@test.local',
      changes: { id: 'admin_coverage_refresh', task: 'monitor_coverage_health', cron: '0 * * * *' },
      timestamp: '2026-02-17T08:00:00Z',
    },
    {
      id: 2,
      schedule_id: 'admin_coverage_refresh',
      action: 'updated',
      actor: 'admin@test.local',
      changes: { cron: { old: '0 * * * *', new: '30 * * * *' } },
      timestamp: '2026-02-17T09:00:00Z',
    },
  ],
};

const apiGet = vi.fn().mockImplementation((url: string) => {
  if (url === '/admin/schedules') {
    return Promise.resolve({ data: MOCK_SCHEDULES });
  }
  if (url === '/admin/schedules/preview') {
    return Promise.resolve({ data: { next_runs_utc: ['2026-02-17T10:00:00Z'] } });
  }
  if (url === '/admin/tasks/catalog') {
    return Promise.resolve({ data: { catalog: { market_data: [] } } });
  }
  if (url === '/admin/schedules/history') {
    return Promise.resolve({ data: MOCK_HISTORY });
  }
  return Promise.resolve({ data: {} });
});

vi.mock('../../services/api', () => ({
  default: {
    get: (...args: any[]) => apiGet(...args),
    post: vi.fn().mockResolvedValue({ data: { status: 'ok', sync: {} } }),
    put: vi.fn().mockResolvedValue({
      data: {
        status: 'ok',
        schedule: {
          id: 'admin_coverage_refresh',
          display_name: 'Coverage Health Check',
          group: 'market_data',
          task: 'backend.tasks.market_data_tasks.monitor_coverage_health',
          cron: '0 * * * *',
          timezone: 'UTC',
          enabled: true,
        },
        sync: {},
      },
    }),
    delete: vi.fn().mockResolvedValue({ data: { status: 'ok' } }),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('AdminSchedules', () => {
  beforeEach(() => {
    apiGet.mockClear();
  });

  it('renders schedules with DB + Render badge', async () => {
    renderWithProviders(<AdminSchedules />);

    const headings = await screen.findAllByText('Schedules');
    expect(headings.length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText('DB + Render')).toBeInTheDocument();
  });

  it('shows schedule with friendly cron description', async () => {
    renderWithProviders(<AdminSchedules />);

    expect(await screen.findByText(/Every hour at :00 UTC/i)).toBeInTheDocument();
    expect(await screen.findByText('Coverage Health Check')).toBeInTheDocument();
  });

  it('shows short task name from dotted path', async () => {
    renderWithProviders(<AdminSchedules />);

    expect(await screen.findByText(/monitor_coverage_health/)).toBeInTheDocument();
  });

  it('shows description text under job name', async () => {
    renderWithProviders(<AdminSchedules />);

    await screen.findByText('Coverage Health Check');
    await waitFor(() => {
      expect(screen.getByText(/Measure data freshness/)).toBeInTheDocument();
    });
  });

  it('shows friendly group labels with color coding', async () => {
    const { container } = renderWithProviders(<AdminSchedules />);

    await screen.findByText('Coverage Health Check');
    const html = container.textContent || '';
    expect(html).toContain('Market Data');
    expect(html).toContain('Maintenance');
  });

  it('shows Sync to Render button when sync is enabled', async () => {
    renderWithProviders(<AdminSchedules />);

    expect(await screen.findByText('Sync to Render')).toBeInTheDocument();
  });

  it('renders History toggle button', async () => {
    renderWithProviders(<AdminSchedules />);

    expect(await screen.findByText('History')).toBeInTheDocument();
  });
});
