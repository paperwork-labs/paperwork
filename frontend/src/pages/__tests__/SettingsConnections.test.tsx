import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@/test/testing-library';
import SettingsConnections from '../../pages/SettingsConnections';
import { renderWithProviders } from '../../test/render';

vi.mock('../../services/api', () => {
  return {
    __esModule: true,
    default: {
      get: vi.fn().mockResolvedValue({ data: { data: {} } }),
      post: vi.fn().mockResolvedValue({ data: {} }),
      patch: vi.fn().mockResolvedValue({ data: {} }),
    },
    accountsApi: {
      list: vi.fn().mockResolvedValue([]),
      add: vi.fn().mockResolvedValue({ id: 1 }),
      sync: vi.fn().mockResolvedValue({ status: 'queued', task_id: 't1' }),
      syncStatus: vi.fn().mockResolvedValue({ sync_status: 'completed' }),
      remove: vi.fn().mockResolvedValue({ message: 'ok' }),
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
    appSettings: { market_only_mode: true },
    appSettingsReady: true,
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
  it('opens modal and shows broker logos', async () => {
    renderWithProviders(<SettingsConnections />);
    const btn = screen.getByRole('button', { name: /\+ New connection/i });
    fireEvent.click(btn);
    expect(await screen.findByText(/Choose a broker to connect/i)).toBeInTheDocument();
    // Logos are images, ensure they're present
    const imgs = await screen.findAllByRole('img');
    expect(imgs.length).toBeGreaterThan(0);
  });
});




