import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import ShadowTrades from '../ShadowTrades';

type Scenario = 'loading' | 'error' | 'empty' | 'data';

const { get, scenarioRef } = vi.hoisted(() => {
  const scenarioRef = { mode: 'data' as Scenario };

  const row = {
    id: 101,
    user_id: 1,
    account_id: null,
    symbol: 'ACME',
    side: 'buy',
    order_type: 'market',
    qty: '10',
    limit_price: null,
    tif: null,
    status: 'marked_to_market',
    risk_gate_verdict: { allowed: true },
    intended_fill_price: '100.50',
    intended_fill_at: new Date().toISOString(),
    simulated_pnl: '25.00',
    simulated_pnl_as_of: new Date().toISOString(),
    last_mark_price: '103.00',
    source_order_id: null,
    error_message: null,
    created_at: new Date().toISOString(),
  };
  const summary = {
    user_id: 1,
    total_orders: 1,
    by_status: { marked_to_market: 1 },
    marked: 1,
    unmarked: 0,
    total_simulated_pnl: '25.00',
  };

  const get = vi.fn((url: string) => {
    if (scenarioRef.mode === 'loading') {
      return new Promise(() => {
        /* never resolves */
      });
    }
    if (scenarioRef.mode === 'error') {
      return Promise.reject(new Error('boom'));
    }
    if (url.startsWith('/shadow-trades/pnl-summary')) {
      if (scenarioRef.mode === 'empty') {
        return Promise.resolve({
          data: {
            user_id: 1,
            total_orders: 0,
            by_status: {},
            marked: 0,
            unmarked: 0,
            total_simulated_pnl: '0',
          },
        });
      }
      return Promise.resolve({ data: summary });
    }
    if (scenarioRef.mode === 'empty') {
      return Promise.resolve({
        data: { items: [], total: 0, limit: 100, offset: 0, user_id: 1 },
      });
    }
    return Promise.resolve({
      data: { items: [row], total: 1, limit: 100, offset: 0, user_id: 1 },
    });
  });
  return { get, scenarioRef };
});

vi.mock('@/services/api', () => ({
  default: { get },
}));

describe('ShadowTrades', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    get.mockClear();
    cleanup();
  });

  it('renders a loading skeleton while requests are pending', () => {
    scenarioRef.mode = 'loading';
    renderWithProviders(<ShadowTrades />);
    expect(screen.getByTestId('shadow-trades-loading')).toBeInTheDocument();
  });

  it('shows an error state when the list query fails', async () => {
    scenarioRef.mode = 'error';
    renderWithProviders(<ShadowTrades />);
    await waitFor(() => {
      expect(screen.getByTestId('shadow-trades-error')).toBeInTheDocument();
    });
    expect(screen.getByText(/Unable to load shadow trades/i)).toBeInTheDocument();
  });

  it('shows the empty state when there are no shadow orders', async () => {
    scenarioRef.mode = 'empty';
    renderWithProviders(<ShadowTrades />);
    await waitFor(() => {
      expect(screen.getByTestId('shadow-trades-empty')).toBeInTheDocument();
    });
    expect(screen.getByText(/No shadow orders yet/i)).toBeInTheDocument();
  });

  it('renders the summary, table, and a disabled promote-to-live button', async () => {
    scenarioRef.mode = 'data';
    renderWithProviders(<ShadowTrades />);
    await waitFor(() => {
      expect(screen.getByTestId('shadow-trades-data')).toBeInTheDocument();
    });
    expect(screen.getByTestId('shadow-pnl-summary')).toBeInTheDocument();
    expect(screen.getByTestId('shadow-row-101')).toBeInTheDocument();
    expect(screen.getByText('ACME')).toBeInTheDocument();

    const promote = screen.getByTestId('promote-to-live') as HTMLButtonElement;
    expect(promote.disabled).toBe(true);
    expect(promote.getAttribute('aria-disabled')).toBe('true');
  });
});
