import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen } from '@/test/testing-library';
import SettingsShell from '../../pages/SettingsShell';
import { renderWithProviders } from '../../test/render';

vi.mock('../../context/AuthContext', async () => {
  return {
    useAuth: () => ({
      user: { role: 'admin' },
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
    // Buttons inside the Settings rail carry the item label; cluster headings
    // (Account / Connections / Trading / AI / Privacy / Admin) are plain
    // <p> text, not buttons. See SETTINGS_NAV_STUDY_2026Q2.md for the IA.
    expect(screen.getByRole('button', { name: /Profile/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Preferences/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Notifications/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Brokers/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Historical import/i })).toBeInTheDocument();
    // Breadcrumb row renders above the outlet for every settings page.
    expect(screen.getByTestId('settings-breadcrumb')).toBeInTheDocument();
  });
});




