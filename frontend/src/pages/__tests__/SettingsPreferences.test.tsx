import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test/render';
import SettingsPreferences from '../SettingsPreferences';
import * as apiModule from '../../services/api';

const updateMe = vi.spyOn(apiModule.authApi as any, 'updateMe').mockResolvedValue({});

const refreshMe = vi.fn().mockResolvedValue(undefined);

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
      appSettings: { market_only_mode: true },
      appSettingsReady: true,
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

  it('saves preferences and updates theme preference', async () => {
    const user = userEvent.setup();
    const { container } = renderWithProviders(<SettingsPreferences />);

    const selects = Array.from(container.querySelectorAll('select')) as HTMLSelectElement[];
    if (selects.length < 3) throw new Error(`Expected at least 3 <select> elements, found ${selects.length}`);
    // Page renders selects in DOM order: theme, table density, timezone
    const themeSelect = selects[0];
    const densitySelect = selects[1];
    const tzSelect = selects[2];

    await user.selectOptions(themeSelect, 'dark');
    await user.selectOptions(densitySelect, 'compact');
    await user.selectOptions(tzSelect, 'America/New_York');
    const currencyInput = screen.getByPlaceholderText('USD');
    await user.clear(currencyInput);
    await user.type(currencyInput, 'EUR');

    await waitFor(() => {
      expect(themeSelect.value).toBe('dark');
      expect(densitySelect.value).toBe('compact');
      expect(tzSelect.value).toBe('America/New_York');
      expect((currencyInput as HTMLInputElement).value).toBe('EUR');
    });

    await user.click(screen.getByRole('button', { name: /save preferences/i }));

    await waitFor(() => expect(updateMe).toHaveBeenCalled());
    expect(updateMe).toHaveBeenCalledWith({
      timezone: 'America/New_York',
      currency_preference: 'EUR',
      ui_preferences: {
        color_mode_preference: 'dark',
        table_density: 'compact',
      },
    });
    expect(setColorModePreference).toHaveBeenCalledWith('dark');
    expect(refreshMe).toHaveBeenCalled();
  });
});


