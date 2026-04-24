import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor, cleanup } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test/render';
import SettingsPreferences from '../SettingsPreferences';
import * as apiModule from '../../services/api';

const updateMe = vi.spyOn(apiModule.authApi as any, 'updateMe').mockResolvedValue({});

const refreshMe = vi.fn().mockResolvedValue(undefined);

afterEach(() => cleanup());

// Use `var` so Vitest hoisting doesn't hit TDZ and so `useAuth()` returns a stable object
// (otherwise SettingsPreferences effect runs every render and overwrites local state).
var mockedUser = {
  id: 1,
  username: 'tester',
  email: 'tester@example.com',
  full_name: 'Test User',
  is_active: true,
  timezone: 'UTC',
  currency_preference: 'USD',
  ui_preferences: {
    color_mode_preference: 'system',
    table_density: 'comfortable',
  },
};

vi.mock('../../context/AuthContext', () => {
  return {
    useAuth: () => ({
      user: mockedUser,
      refreshMe,
      ready: true,
    }),
  };
});

// Use `var` so Vitest hoisting doesn't hit TDZ.
var setColorModePreference = vi.fn();

vi.mock('../../theme/colorMode', async () => {
  const actual: any = await vi.importActual('../../theme/colorMode');
  return {
    ...actual,
    useColorMode: () => ({
      colorModePreference: 'system',
      setColorModePreference,
    }),
  };
});

describe('SettingsPreferences', () => {
  beforeEach(() => {
    updateMe.mockClear();
    refreshMe.mockClear();
    setColorModePreference.mockClear();
  });

  it('auto-saves theme change immediately', async () => {
    const user = userEvent.setup();
    const { container } = renderWithProviders(<SettingsPreferences />);

    const selects = Array.from(container.querySelectorAll('select')) as HTMLSelectElement[];
    const themeSelect = selects[0];

    await user.selectOptions(themeSelect, 'dark');

    // Theme should apply locally right away
    expect(setColorModePreference).toHaveBeenCalledWith('dark');

    // Should auto-save to backend
    await waitFor(() => expect(updateMe).toHaveBeenCalled());
    expect(updateMe).toHaveBeenCalledWith(
      expect.objectContaining({
        ui_preferences: expect.objectContaining({ color_mode_preference: 'dark' }),
      }),
    );
    expect(refreshMe).toHaveBeenCalled();
  });

  it('auto-saves timezone change immediately', async () => {
    const user = userEvent.setup();
    const { container } = renderWithProviders(<SettingsPreferences />);

    const selects = Array.from(container.querySelectorAll('select')) as HTMLSelectElement[];
    const tzSelect = selects[2];

    await user.selectOptions(tzSelect, 'America/New_York');

    await waitFor(() => expect(updateMe).toHaveBeenCalled());
    expect(updateMe).toHaveBeenCalledWith({ timezone: 'America/New_York' });
  });

  it('auto-saves currency after debounce when 3 chars entered', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPreferences />);

    const currencyInput = screen.getByPlaceholderText('USD');
    await user.clear(currencyInput);
    await user.type(currencyInput, 'EUR');

    // Should debounce, then auto-save
    await waitFor(() => expect(updateMe).toHaveBeenCalled(), { timeout: 3000 });
    expect(updateMe).toHaveBeenCalledWith({ currency_preference: 'EUR' });
  });

  it('shows "Saved" badge after successful save', async () => {
    const user = userEvent.setup();
    const { container } = renderWithProviders(<SettingsPreferences />);

    const selects = Array.from(container.querySelectorAll('select')) as HTMLSelectElement[];
    await user.selectOptions(selects[1], 'compact');

    await waitFor(() => {
      expect(screen.getByText('Saved')).toBeInTheDocument();
    });
  });

  it('does not show a Save button (auto-save replaces it)', () => {
    renderWithProviders(<SettingsPreferences />);
    expect(screen.queryByRole('button', { name: /save preferences/i })).toBeNull();
  });
});
