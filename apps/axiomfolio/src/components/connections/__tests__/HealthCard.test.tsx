import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';
import { HealthCard } from '../HealthCard';
import { renderWithProviders } from '@/test/render';
import type { ConnectionsHealthResponse } from '@/services/connectionsHealth';

const baseHealth: ConnectionsHealthResponse = {
  connected: 2,
  total: 6,
  last_sync_at: '2026-01-15T12:00:00.000Z',
  by_broker: [
    { broker: 'ibkr', status: 'connected', last_sync_at: '2026-01-15T12:00:00.000Z', error_message: null },
    { broker: 'schwab', status: 'stale', last_sync_at: null, error_message: 'expired' },
    { broker: 'tastytrade', status: 'disconnected', last_sync_at: null, error_message: null },
    { broker: 'etrade', status: 'disconnected', last_sync_at: null, error_message: null },
    { broker: 'tradier', status: 'disconnected', last_sync_at: null, error_message: null },
    { broker: 'coinbase', status: 'disconnected', last_sync_at: null, error_message: null },
  ],
};

describe('HealthCard', () => {
  it('renders connected counts and run sync', async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    renderWithProviders(
      <HealthCard health={baseHealth} onRunSync={onRun} syncPending={false} />,
    );
    expect(screen.getByText(/2/)).toBeInTheDocument();
    expect(screen.getByText(/of 6 brokers connected/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /charles schwab/i })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /run sync now/i }));
    expect(onRun).toHaveBeenCalledTimes(1);
  });
});
