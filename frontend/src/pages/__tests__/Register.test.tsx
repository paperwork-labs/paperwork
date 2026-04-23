import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, screen } from '@/test/testing-library';

import { renderWithProviders } from '../../test/render';
import Register from '../Register';

const register = vi.fn();

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    register,
    ready: true,
  }),
}));

describe('Register', () => {
  beforeEach(() => {
    cleanup();
    register.mockClear();
    localStorage.removeItem('pending_upgrade_tier');
  });

  it('shows Pro+ upgrade microcopy when URL has upgrade=pro_plus', () => {
    renderWithProviders(<Register />, { route: '/register?upgrade=pro_plus' });
    expect(screen.getByText(/You're upgrading to/i)).toBeInTheDocument();
    expect(screen.getByText('Pro+')).toBeInTheDocument();
    expect(localStorage.getItem('pending_upgrade_tier')).toBe('pro_plus');
  });
});
