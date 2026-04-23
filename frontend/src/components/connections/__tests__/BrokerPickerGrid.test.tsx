import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';
import { BrokerPickerGrid } from '../BrokerPickerGrid';
import { renderWithProviders } from '@/test/render';
import type { ConnectionsHealthBrokerRow } from '@/services/connectionsHealth';
import type { BrokerSlug } from '../brokerCatalog';

const byBroker: ConnectionsHealthBrokerRow[] = [
  { broker: 'ibkr', status: 'disconnected', last_sync_at: null, error_message: null },
  { broker: 'schwab', status: 'disconnected', last_sync_at: null, error_message: null },
  { broker: 'tastytrade', status: 'disconnected', last_sync_at: null, error_message: null },
  { broker: 'etrade', status: 'disconnected', last_sync_at: null, error_message: null },
  { broker: 'tradier', status: 'disconnected', last_sync_at: null, error_message: null },
  { broker: 'coinbase', status: 'disconnected', last_sync_at: null, error_message: null },
];

const emptySlug = (): Record<BrokerSlug, boolean> => ({
  ibkr: false,
  schwab: false,
  tastytrade: false,
  etrade: false,
  tradier: false,
  coinbase: false,
  plaid: false,
});

const emptyRel = (): Record<BrokerSlug, string | null> => ({
  ibkr: null,
  schwab: null,
  tastytrade: null,
  etrade: null,
  tradier: null,
  coinbase: null,
  plaid: null,
});

describe('BrokerPickerGrid', () => {
  it('invokes onConnect when Connect is clicked', async () => {
    const user = userEvent.setup();
    const onConnect = vi.fn();
    const onReconnect = vi.fn();
    const onManage = vi.fn();

    renderWithProviders(
      <BrokerPickerGrid
        byBroker={byBroker}
        hasAccountsBySlug={emptySlug()}
        relativeLastSyncBySlug={emptyRel()}
        onConnect={onConnect}
        onReconnect={onReconnect}
        onManage={onManage}
        schwabConfigured
      />,
    );

    const connectButtons = screen.getAllByRole('button', { name: /^connect$/i });
    expect(connectButtons.length).toBeGreaterThan(0);
    await user.click(connectButtons[0]!);
    expect(onConnect).toHaveBeenCalledTimes(1);
    expect(onReconnect).not.toHaveBeenCalled();
    expect(onManage).not.toHaveBeenCalled();
  });
});
