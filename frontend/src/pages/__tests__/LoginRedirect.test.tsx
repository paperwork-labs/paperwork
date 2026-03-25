import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test/render';
import Login from '../Login';

const login = vi.fn().mockResolvedValue(undefined);
const navigate = vi.fn();

// Use `var` so Vitest hoisting doesn't hit TDZ.
var locationState: any = { state: {} };

vi.mock('../../context/AuthContext', () => {
  return {
    useAuth: () => ({
      login,
      ready: true,
      appSettings: { market_only_mode: true },
      appSettingsReady: true,
    }),
  };
});

vi.mock('react-router-dom', async () => {
  const actual: any = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
    useLocation: () => locationState,
  };
});

describe('Login redirect', () => {
  beforeEach(() => {
    cleanup();
    login.mockClear();
    navigate.mockClear();
    locationState = { state: {} };
    localStorage.removeItem('qm.ui.last_route');
  });

  it('redirects to saved last route after login when no state.from exists', async () => {
    const user = userEvent.setup();
    localStorage.setItem('qm.ui.last_route', '/market/coverage');

    renderWithProviders(<Login />);

    await user.type(screen.getByPlaceholderText('you@example.com'), 'demo@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'pw');
    await user.click(screen.getByRole('button', { name: /^log in$/i }));

    await waitFor(() => expect(login).toHaveBeenCalled());
    expect(navigate).toHaveBeenCalledWith('/market/coverage', { replace: true });
  });

  it('prefers state.from over saved route', async () => {
    const user = userEvent.setup();
    localStorage.setItem('qm.ui.last_route', '/settings/profile');
    locationState = { state: { from: { pathname: '/market/tracked', search: '', hash: '' } } };

    renderWithProviders(<Login />);

    await user.type(screen.getByPlaceholderText('you@example.com'), 'demo@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'pw');
    await user.click(screen.getByRole('button', { name: /^log in$/i }));

    await waitFor(() => expect(login).toHaveBeenCalled());
    expect(navigate).toHaveBeenCalledWith('/market/tracked', { replace: true });
  });
});


