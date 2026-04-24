import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import StageScan from '../StageScan';

type Scenario = 'loading' | 'error' | 'empty' | 'data';

const { getSnapshotTable, scenarioRef } = vi.hoisted(() => {
  const scenarioRef = { mode: 'data' as Scenario };
  const getSnapshotTable = vi.fn(() => {
    if (scenarioRef.mode === 'error') {
      return Promise.reject(new Error('500'));
    }
    if (scenarioRef.mode === 'loading') {
      return new Promise(() => {
        /* never resolves */
      });
    }
    if (scenarioRef.mode === 'empty') {
      return Promise.resolve({ rows: [], total: 0 });
    }
    return Promise.resolve({
      rows: [
        {
          symbol: 'AAPL',
          stage_label: '2B',
          current_stage_days: 22,
          current_price: 187.5,
          perf_20d: 4.2,
          rs_mansfield_pct: 18.7,
          sector: 'Technology',
          industry: 'Consumer Electronics',
          action_label: 'BUY',
        },
        {
          symbol: 'MSFT',
          stage_label: '2B',
          current_stage_days: 40,
          current_price: 432.1,
          perf_20d: 2.1,
          rs_mansfield_pct: 11.5,
          sector: 'Technology',
          industry: 'Software',
          action_label: 'HOLD',
        },
      ],
      total: 2,
    });
  });
  return { getSnapshotTable, scenarioRef };
});

vi.mock('@/services/api', () => ({
  default: { get: vi.fn() },
  marketDataApi: {
    getSnapshotTable,
  },
}));

describe('signals/StageScan', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSnapshotTable.mockClear();
    cleanup();
  });

  it('renders loading skeletons while the request is pending', () => {
    scenarioRef.mode = 'loading';
    renderWithProviders(<StageScan />);
    expect(screen.getByTestId('scan-loading')).toBeInTheDocument();
  });

  it('renders an error card with retry when the request fails', async () => {
    scenarioRef.mode = 'error';
    renderWithProviders(<StageScan />);
    await waitFor(() => {
      expect(screen.getByTestId('scan-error')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('renders the empty state with a link to Tracked when the stage has no rows', async () => {
    scenarioRef.mode = 'empty';
    renderWithProviders(<StageScan />);
    await waitFor(() => {
      expect(screen.getByTestId('scan-empty')).toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: /open tracked universe/i })).toHaveAttribute(
      'href',
      '/market/tracked',
    );
  });

  it('renders rows with symbol, stage, RS, and action when data is present', async () => {
    scenarioRef.mode = 'data';
    renderWithProviders(<StageScan />);
    expect(await screen.findByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
    expect(screen.getByText('BUY')).toBeInTheDocument();
    expect(screen.getByText('HOLD')).toBeInTheDocument();
    expect(screen.getByText('18.7%')).toBeInTheDocument();
  });
});
