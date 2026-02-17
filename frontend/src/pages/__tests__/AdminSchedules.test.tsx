import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor, cleanup } from '@testing-library/react';
import AdminSchedules from '../../pages/AdminSchedules';
import { renderWithProviders } from '../../test/render';

afterEach(() => cleanup());

const MOCK_SCHEDULES = {
  schedules: [
    {
      name: 'admin_coverage_refresh',
      task: 'backend.tasks.market_data_tasks.monitor_coverage_health',
      cron: '0 * * * *',
      timezone: 'UTC',
      enabled: true,
      status: 'active',
      source: 'redbeat',
      last_run_at: '2026-02-17T09:00:00Z',
      total_run_count: 19,
      last_run: { task_name: 'admin_coverage_refresh', status: 'success', started_at: '2026-02-17T09:00:00Z' },
    },
  ],
  mode: 'redbeat',
};

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    currency: 'USD',
    timezone: 'America/Los_Angeles',
    tableDensity: 'comfortable',
  }),
}));

const apiGet = vi.fn().mockImplementation((url: string) => {
  if (url === '/admin/schedules') {
    return Promise.resolve({ data: MOCK_SCHEDULES });
  }
  if (url === '/admin/schedules/preview') {
    return Promise.resolve({ data: { next_runs_utc: ['2026-02-17T10:00:00Z'] } });
  }
  return Promise.resolve({ data: {} });
});

vi.mock('../../services/api', () => ({
  default: {
    get: (...args: any[]) => apiGet(...args),
    post: vi.fn(),
    delete: vi.fn(),
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

  it('renders schedule with friendly description and run count', async () => {
    renderWithProviders(<AdminSchedules />);

    expect(await screen.findByText('Schedules')).toBeInTheDocument();
    expect(await screen.findByText(/Every hour at :00 UTC/i)).toBeInTheDocument();
    expect(await screen.findByText('admin_coverage_refresh')).toBeInTheDocument();
    expect(screen.getByText('19')).toBeInTheDocument();
  });

  it('shows RedBeat badge when mode is redbeat', async () => {
    renderWithProviders(<AdminSchedules />);

    expect(await screen.findByText('RedBeat')).toBeInTheDocument();
  });

  it('shows short task name from full dotted path', async () => {
    renderWithProviders(<AdminSchedules />);

    expect(await screen.findByText(/monitor_coverage_health/)).toBeInTheDocument();
  });
});
