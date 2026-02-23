import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@/test/testing-library';
import { renderWithProviders } from '../../test/render';
import SettingsProfile from '../SettingsProfile';
import * as apiModule from '../../services/api';

const updateMe = vi.spyOn(apiModule.authApi as any, 'updateMe').mockResolvedValue({});
const changePassword = vi.spyOn(apiModule.authApi as any, 'changePassword').mockResolvedValue({});

const refreshMe = vi.fn().mockResolvedValue(undefined);

vi.mock('../../context/AuthContext', () => {
  return {
    useAuth: () => ({
      user: {
        id: 1,
        username: 'tester',
        email: 'tester@example.com',
        full_name: 'Test User',
        is_active: true,
        has_password: true,
      },
      refreshMe,
      appSettings: { market_only_mode: true },
      appSettingsReady: true,
      ready: true,
    }),
  };
});

describe('SettingsProfile', () => {
  beforeEach(() => {
    updateMe.mockClear();
    changePassword.mockClear();
    refreshMe.mockClear();
  });

  it('updates email with current_password', async () => {
    renderWithProviders(<SettingsProfile />);

    fireEvent.change(screen.getByPlaceholderText('name@domain.com'), {
      target: { value: 'new@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Current password for email change'), {
      target: { value: 'Passw0rd!' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(updateMe).toHaveBeenCalled());
    expect(updateMe).toHaveBeenCalledWith({
      email: 'new@example.com',
      current_password: 'Passw0rd!',
    });
    expect(refreshMe).toHaveBeenCalled();
  });

  it('changes password with current_password and new_password', async () => {
    renderWithProviders(<SettingsProfile />);

    // Current password (Password section)
    const pw = screen.getAllByLabelText('Current password for password change');
    for (const el of pw) {
      fireEvent.change(el, { target: { value: 'OldPassw0rd!' } });
    }

    // New password & confirm are placeholders "At least 8 characters" and "Repeat new password"
    const newPwInputs = screen.getAllByPlaceholderText('At least 8 characters');
    fireEvent.change(newPwInputs[0], { target: { value: 'NewPassw0rd!' } });
    const confirmPwInputs = screen.getAllByPlaceholderText('Repeat new password');
    fireEvent.change(confirmPwInputs[0], { target: { value: 'NewPassw0rd!' } });
    const changeButtons = screen.getAllByRole('button', { name: /change password/i });
    fireEvent.click(changeButtons[0]);

    await waitFor(() => expect(changePassword).toHaveBeenCalled());
    expect(changePassword).toHaveBeenCalledWith({
      current_password: 'OldPassw0rd!',
      new_password: 'NewPassw0rd!',
    });
  });
});


