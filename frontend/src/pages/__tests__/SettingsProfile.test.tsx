import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { screen, fireEvent, waitFor } from '@/test/testing-library';
import { ColorModeProvider } from '../../theme/colorMode';
import { createTestQueryClient, renderWithProviders } from '../../test/render';
import SettingsProfile from '../SettingsProfile';
import * as apiModule from '../../services/api';

const updateMe = vi.spyOn(apiModule.authApi as any, 'updateMe').mockResolvedValue({});
const changePassword = vi.spyOn(apiModule.authApi as any, 'changePassword').mockResolvedValue({});

const refreshMe = vi.fn().mockResolvedValue(undefined);

const defaultUser = {
  id: 1,
  username: 'tester',
  email: 'tester@example.com',
  full_name: 'Test User',
  is_active: true,
  has_password: true,
};

let mockUser: typeof defaultUser | null = defaultUser;

vi.mock('../../context/AuthContext', () => {
  return {
    useAuth: () => ({
      user: mockUser,
      refreshMe,
      appSettings: { market_only_mode: true },
      appSettingsReady: true,
      ready: true,
    }),
  };
});

describe('SettingsProfile', () => {
  beforeEach(() => {
    mockUser = defaultUser;
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

  it('username tooltip wrapper is keyboard-focusable and exposes tooltip content', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsProfile />);

    const fullName = screen.getByPlaceholderText('Your name');
    fullName.focus();
    await user.tab({ shift: true });

    const wrap = screen.getByTestId('profile-username-focus-target');
    expect(wrap.tagName.toLowerCase()).toBe('span');
    expect(wrap).toHaveAttribute('role', 'group');
    expect(wrap).toHaveAttribute('aria-label', 'Username');
    expect(wrap).toHaveFocus();

    const tooltipLines = await screen.findAllByText(
      'Usernames are set at signup. Contact support if you need to change yours.',
    );
    expect(tooltipLines.length).toBeGreaterThan(0);
    expect(tooltipLines[0]).toBeInTheDocument();
  });

  it('does not show email-change current password field when user hydrates after mount', () => {
    const queryClient = createTestQueryClient();
    const wrap = (ui: React.ReactElement) => (
      <QueryClientProvider client={queryClient}>
        <ColorModeProvider>
          <MemoryRouter>
            {ui}
          </MemoryRouter>
        </ColorModeProvider>
      </QueryClientProvider>
    );

    mockUser = null;
    const { rerender } = render(wrap(<SettingsProfile />));
    expect(screen.queryByLabelText('Current password for email change')).not.toBeInTheDocument();

    mockUser = { ...defaultUser };
    rerender(wrap(<SettingsProfile />));

    expect(screen.queryByLabelText('Current password for email change')).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText('name@domain.com')).toHaveValue('tester@example.com');
  });
});


