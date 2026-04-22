import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen, waitFor } from '@/test/testing-library';
import { renderWithProviders } from '../../../test/render';
import PortfolioOrders from '../PortfolioOrders';

const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));

vi.mock('@/services/api', () => ({
  default: { get: getMock },
  handleApiError: (e: unknown) => String(e),
}));

vi.mock('@/hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({ currency: 'USD', timezone: 'America/New_York' }),
}));

describe('PortfolioOrders', () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it('shows Placed and Broker badges from list provenance', async () => {
    getMock.mockImplementation(() =>
      Promise.resolve({
        data: {
          data: [
          {
            id: 1,
            symbol: 'AAPL',
            side: 'buy',
            order_type: 'market',
            status: 'filled',
            quantity: 1,
            limit_price: null,
            stop_price: null,
            filled_quantity: 1,
            filled_avg_price: 100,
            account_id: null,
            broker_order_id: null,
            strategy_id: null,
            signal_id: null,
            position_id: null,
            user_id: 1,
            source: 'manual',
            broker_type: 'ibkr',
            estimated_commission: null,
            estimated_margin_impact: null,
            preview_data: null,
            error_message: null,
            submitted_at: null,
            filled_at: '2020-01-01T00:00:00Z',
            cancelled_at: null,
            created_at: '2020-01-01T00:00:00Z',
            created_by: null,
            provenance: 'app',
          },
          {
            id: -9,
            symbol: 'XOM',
            side: 'buy',
            order_type: 'market',
            status: 'filled',
            quantity: 2,
            limit_price: null,
            stop_price: null,
            filled_quantity: 2,
            filled_avg_price: 50,
            account_id: 'SCH-1',
            broker_order_id: 'b1',
            strategy_id: null,
            signal_id: null,
            position_id: null,
            user_id: 1,
            source: 'manual',
            broker_type: 'schwab',
            estimated_commission: null,
            estimated_margin_impact: null,
            preview_data: null,
            error_message: null,
            submitted_at: null,
            filled_at: '2020-01-02T00:00:00Z',
            cancelled_at: null,
            created_at: '2020-01-02T00:00:00Z',
            created_by: null,
            provenance: 'broker_sync',
          },
        ],
      },
    }),
    );

    renderWithProviders(<PortfolioOrders />, { route: '/portfolio/orders' });
    await waitFor(() => {
      expect(screen.getAllByText('Placed').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText('Broker').length).toBeGreaterThan(0);
  });

  it('passes source=broker when Broker list filter is selected', async () => {
    getMock.mockImplementation(() => Promise.resolve({ data: { data: [] } }));
    const user = userEvent.setup();
    renderWithProviders(<PortfolioOrders />, { route: '/portfolio/orders' });
    await screen.findByRole('button', { name: 'Broker' });
    expect(
      (getMock.mock.calls[0] as [string, { params: Record<string, string> }])[1].params.source,
    ).toBe('all');
    await user.click(screen.getByRole('button', { name: 'Broker' }));
    await waitFor(() => {
      expect(
        (getMock.mock.calls[getMock.mock.calls.length - 1] as [string, { params: Record<string, string> }])[1]
          .params.source,
      ).toBe('broker');
    });
  });
});
