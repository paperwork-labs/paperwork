import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';
import AdminJobs from '../AdminJobs';
import { renderWithProviders } from '../../test/render';

const apiGet = vi.fn();

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    currency: 'USD',
    timezone: 'UTC',
    tableDensity: 'comfortable',
  }),
}));

vi.mock('../../services/api', () => {
  return {
    default: {
      get: (...args: any[]) => apiGet(...args),
    },
  };
});

vi.mock('react-hot-toast', () => ({
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe('AdminJobs', () => {
  beforeEach(() => {
    apiGet.mockReset();
  });

  it('loads first page with default paging params and coverage filter', async () => {
    apiGet.mockResolvedValueOnce({
      data: { jobs: [{ id: 1, task_name: 'admin_backfill_daily', status: 'ok' }], total: 200 },
    });

    renderWithProviders(<AdminJobs />);

    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledWith('/market-data/admin/jobs', {
        params: { limit: 25, offset: 0, exclude_task: 'admin_coverage_refresh' },
      });
    });

    expect(await screen.findByText(/Admin Jobs/i)).toBeInTheDocument();
    expect(screen.getByText(/admin_backfill_daily/i)).toBeInTheDocument();
  });

  it('changes page size via pagination menu and refetches', async () => {
    apiGet
      .mockResolvedValueOnce({ data: { jobs: [], total: 4585 } }) // initial
      .mockResolvedValueOnce({ data: { jobs: [], total: 4585 } }); // after page size change

    renderWithProviders(<AdminJobs />);

    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledWith('/market-data/admin/jobs', {
        params: { limit: 25, offset: 0, exclude_task: 'admin_coverage_refresh' },
      });
    });

    const user = userEvent.setup();
    await user.click(screen.getAllByRole('button', { name: /Page size/i })[0]);
    await user.click(screen.getByRole('menuitem', { name: /50 per page/i }));

    await waitFor(() => {
      expect(apiGet).toHaveBeenLastCalledWith('/market-data/admin/jobs', {
        params: { limit: 50, offset: 0, exclude_task: 'admin_coverage_refresh' },
      });
    });
  });

  it('opens details dialog from row action', async () => {
    apiGet.mockResolvedValueOnce({
      data: {
        jobs: [
          {
            id: 1,
            task_name: 'market_universe_tracked_refresh',
            status: 'ok',
            params: { foo: 'bar' },
            counters: { symbols_processed: 12 },
            error: null,
          },
        ],
        total: 1,
      },
    });

    renderWithProviders(<AdminJobs />);

    expect(await screen.findByText(/market_universe_tracked_refresh/i)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /Details/i })[0]);
    expect(await screen.findByText(/Job details/i)).toBeInTheDocument();
    expect(screen.getByText(/Params/i)).toBeInTheDocument();
    expect(screen.getByText(/Counters/i)).toBeInTheDocument();
  });
});


