import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';
import { within } from '@testing-library/react';
import SettingsConnections from '../../pages/SettingsConnections';
import { renderWithProviders } from '../../test/render';

vi.mock('../../services/api', () => {
  const healthPayload = {
    connected: 0,
    total: 6,
    last_sync_at: null as string | null,
    by_broker: ['ibkr', 'schwab', 'tastytrade', 'etrade', 'tradier', 'coinbase'].map((broker) => ({
      broker,
      status: 'disconnected' as const,
      last_sync_at: null as string | null,
      error_message: null as string | null,
    })),
  };
  return {
    __esModule: true,
    default: {
      get: vi.fn().mockImplementation((url: string) => {
        const u = String(url);
        if (u.includes('connections/health')) return Promise.resolve({ data: healthPayload });
        if (u.includes('oauth/connections')) return Promise.resolve({ data: { connections: [] } });
        if (u.includes('gateway-status')) return Promise.resolve({ data: { data: { connected: false, available: true } } });
        return Promise.resolve({ data: { data: {} } });
      }),
      post: vi.fn().mockResolvedValue({ data: {} }),
      patch: vi.fn().mockResolvedValue({ data: {} }),
    },
    accountsApi: {
      list: vi.fn().mockResolvedValue([]),
      syncHistory: vi.fn().mockResolvedValue([]),
      add: vi.fn().mockResolvedValue({ id: 1 }),
      sync: vi.fn().mockResolvedValue({ status: 'queued', task_id: 't1' }),
      syncStatus: vi.fn().mockResolvedValue({ sync_status: 'completed' }),
      remove: vi.fn().mockResolvedValue({ message: 'ok' }),
      updateAccount: vi.fn().mockResolvedValue({}),
      updateCredentials: vi.fn().mockResolvedValue({}),
    },
    aggregatorApi: {
      config: vi.fn().mockResolvedValue({ schwab: { configured: true, redirect_uri: 'https://example.com/cb' } }),
      // First status call → disconnected; subsequent calls → job success/connected
      tastytradeStatus: vi
        .fn()
        .mockResolvedValueOnce({ available: true, connected: false })
        .mockResolvedValue({ job_state: 'success', connected: true }),
      tastytradeConnect: vi.fn().mockResolvedValue({ job_id: 'job1' }),
      tastytradeDisconnect: vi.fn().mockResolvedValue({}),
      ibkrFlexConnect: vi.fn().mockResolvedValue({ job_id: 'job2' }),
      ibkrFlexStatus: vi.fn().mockResolvedValue({ connected: true, accounts: [{ id: 99, account_number: 'U12345678' }] }),
      schwabLink: vi.fn().mockResolvedValue({ url: 'https://auth.example/authorize' }),
      schwabProbe: vi.fn().mockResolvedValue({}),
    },
    handleApiError: (e: any) => String(e?.message || 'error'),
  };
});

vi.mock('../../context/AuthContext', async () => {
  const mockAuth = {
    user: { id: 1, username: 'u', email: 'e', is_active: true, role: 'admin' },
    ready: true,
  };
  return {
    useAuth: () => mockAuth,
    useAuthOptional: () => mockAuth,
  };
});

vi.mock('../../context/AccountContext', () => ({
  useAccountContext: () => ({
    accounts: [],
    loading: false,
    error: null,
    selected: 'all',
    setSelected: vi.fn(),
    refetch: vi.fn(),
  }),
}));

describe('Brokerages wizard', () => {
  it(
    'opens modal and shows broker logos',
    async () => {
      const user = userEvent.setup();
      renderWithProviders(<SettingsConnections />);
      const btn = screen.getByRole('button', { name: /\+ New connection/i });
      await user.click(btn);
      const dialog = await screen.findByRole('dialog', {}, { timeout: 10_000 });
      expect(
        await within(dialog).findByText(/Choose a broker to connect/i, {}, { timeout: 10_000 }),
      ).toBeInTheDocument();
      // Wizard step 1: three broker tiles (local SVG + " logo" in accessible name)
      expect(within(dialog).getByRole('img', { name: 'Charles Schwab logo' })).toBeInTheDocument();
      expect(within(dialog).getByRole('img', { name: 'Tastytrade logo' })).toBeInTheDocument();
      expect(within(dialog).getByRole('img', { name: 'Interactive Brokers logo' })).toBeInTheDocument();
    },
    15_000,
  );
});




