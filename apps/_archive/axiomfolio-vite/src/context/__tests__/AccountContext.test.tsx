import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, render, screen, waitFor } from '@/test/testing-library';

import { AccountProvider, useAccountContext } from '../AccountContext';

const mockApiGet = vi.fn();
let mockedAuth: any = {
  token: 'token',
  ready: true,
  user: { role: 'user' },
};

vi.mock('../AuthContext', () => ({
  useAuth: () => mockedAuth,
}));

vi.mock('../../services/api', () => ({
  default: {
    get: (...args: any[]) => mockApiGet(...args),
  },
}));

const Probe: React.FC = () => {
  const { accounts, loading, error } = useAccountContext();
  return (
    <div>
      <span data-testid="accounts">{accounts.length}</span>
      <span data-testid="loading">{loading ? 'yes' : 'no'}</span>
      <span data-testid="error">{error || ''}</span>
    </div>
  );
};

describe('AccountProvider', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    localStorage.clear();
    mockedAuth = {
      token: 'token',
      ready: true,
      user: { role: 'user' },
    };
  });

  it('does not call /accounts when logged out', async () => {
    mockedAuth = { token: null, ready: true, user: null };
    render(
      <AccountProvider>
        <Probe />
      </AccountProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('accounts').textContent).toBe('0');
      expect(screen.getByTestId('loading').textContent).toBe('no');
    });
    expect(mockApiGet).not.toHaveBeenCalled();
  });

  it('calls /accounts when authenticated', async () => {
    mockApiGet.mockResolvedValue({
      data: [{ id: 1, account_number: 'U123', account_name: 'IBKR Main' }],
    });

    render(
      <AccountProvider>
        <Probe />
      </AccountProvider>
    );

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/accounts');
    });
    await waitFor(() => {
      expect(screen.getByTestId('accounts').textContent).toBe('1');
      expect(screen.getByTestId('error').textContent).toBe('');
    });
  });
});
