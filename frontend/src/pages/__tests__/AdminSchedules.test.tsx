import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import AdminSchedules from '../../pages/AdminSchedules';
import { renderWithProviders } from '../../test/render';

const apiGet = vi.fn((url: string) => {
  if (url === '/admin/schedules') {
    return Promise.resolve({
      data: {
        schedules: [
          {
            name: 'monitor-coverage-health-hourly',
            task: 'backend.tasks.market_data_tasks.monitor_coverage_health',
            cron: '0 * * * *',
            timezone: 'UTC',
            enabled: true,
            status: 'active',
          },
        ],
        mode: 'redbeat',
      },
    });
  }
  if (url === '/admin/schedules/preview') {
    return Promise.resolve({ data: { next_runs_utc: ['2026-01-14T10:00:00Z'] } });
  }
  return Promise.resolve({ data: {} });
});

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    currency: 'USD',
    timezone: 'America/Los_Angeles',
    tableDensity: 'comfortable',
  }),
}));

vi.mock('../../services/api', () => {
  return {
    default: {
      get: (url: string) => apiGet(url),
      post: vi.fn(),
      delete: vi.fn(),
    },
  };
});

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('AdminSchedules', () => {
  it('renders a friendly schedule description with next run', async () => {
    renderWithProviders(<AdminSchedules />);

    await waitFor(() => {
      expect(screen.getByText(/Schedule \(friendly\)/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Every hour at :00 UTC/i)).toBeInTheDocument();
    expect(screen.getByText(/Next:/i)).toBeInTheDocument();
  });
});

