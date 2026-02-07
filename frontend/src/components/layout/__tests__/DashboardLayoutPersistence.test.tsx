import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import DashboardLayout from '../DashboardLayout';

// Mock Auth + Account context dependencies.
vi.mock('../../../context/AuthContext', () => {
  return {
    useAuth: () => ({
      user: { username: 'tester' },
      logout: vi.fn(),
    }),
  };
});

vi.mock('../../../context/AccountContext', () => {
  return {
    useAccountContext: () => ({
      accounts: [],
      loading: false,
      selected: 'all',
      setSelected: vi.fn(),
    }),
  };
});

// Ensure desktop path so sidebar exists.
vi.mock('@chakra-ui/react', async () => {
  const actual: any = await vi.importActual('@chakra-ui/react');
  return {
    ...actual,
    useMediaQuery: () => [true],
  };
});

// Avoid network calls made on mount.
vi.mock('../../../services/api', () => {
  return {
    portfolioApi: {
      getLive: vi.fn().mockResolvedValue({ data: { accounts: {} } }),
    },
  };
});

describe('DashboardLayout sidebar persistence', () => {
  beforeEach(() => {
    localStorage.removeItem('qm.ui.sidebar_open');
  });

  it('reads collapsed state from localStorage and persists on toggle', async () => {
    const user = userEvent.setup();
    localStorage.setItem('qm.ui.sidebar_open', '0');

    renderWithProviders(<DashboardLayout />);

    // When collapsed, brand text should be hidden.
    expect(screen.queryByText('AxiomFolio')).toBeNull();

    await user.click(screen.getByRole('button', { name: /menu/i }));

    expect(localStorage.getItem('qm.ui.sidebar_open')).toBe('1');
  });
});


