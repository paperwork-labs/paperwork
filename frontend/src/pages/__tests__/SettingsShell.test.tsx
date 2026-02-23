import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen } from '@/test/testing-library';
import SettingsShell from '../../pages/SettingsShell';
import { renderWithProviders } from '../../test/render';

vi.mock('../../context/AuthContext', async () => {
  return {
    useAuth: () => ({
      user: { role: 'admin' },
      appSettings: { market_only_mode: true },
      appSettingsReady: true,
      ready: true,
    }),
  };
});

vi.mock('../../services/api', () => {
  return {
    default: {
      get: vi.fn().mockResolvedValue({ data: { meta: { exposed_to_all: true } } }),
    },
  };
});

describe('SettingsShell', () => {
  it('renders sidebar sections', () => {
    renderWithProviders(<SettingsShell />, { route: '/settings' });
    // On small screens SettingsShell collapses to an icon rail, so links are aria-labels.
    expect(screen.getByRole('button', { name: /Profile/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Preferences/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Notifications/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Brokerages/i })).toBeInTheDocument();
  });
});




