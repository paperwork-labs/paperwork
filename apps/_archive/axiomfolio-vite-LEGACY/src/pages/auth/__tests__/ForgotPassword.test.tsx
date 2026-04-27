import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { cleanup, screen } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';

import { renderWithProviders } from '../../../test/render';
import ForgotPassword from '../ForgotPassword';

describe('ForgotPassword', () => {
  beforeEach(() => {
    cleanup();
  });

  it('submitting the form shows the friendly success message even with empty email', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ForgotPassword />, { route: '/auth/forgot-password' });

    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(
      screen.getByText(/If an account exists with that email/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/support@axiomfolio\.com/i)).toBeInTheDocument();
  });
});
