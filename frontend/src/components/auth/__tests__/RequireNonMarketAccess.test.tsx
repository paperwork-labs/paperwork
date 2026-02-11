import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

import { renderWithProviders } from '../../../test/render';
import RequireNonMarketAccess from '../RequireNonMarketAccess';

var mockedAuth: any = {
  user: { role: 'user' },
  appSettings: { market_only_mode: true },
  ready: true,
  appSettingsReady: true,
};

vi.mock('../../../context/AuthContext', () => {
  return {
    useAuth: () => mockedAuth,
  };
});

const AppRoutes = () => (
  <Routes>
    <Route element={<RequireNonMarketAccess section="portfolio" />}>
      <Route path="/portfolio" element={<div>Portfolio page</div>} />
    </Route>
    <Route path="/" element={<div>Market page</div>} />
  </Routes>
);

describe('RequireNonMarketAccess', () => {
  afterEach(() => {
    cleanup();
  });

  it('redirects non-admin users when market-only mode is enabled', () => {
    mockedAuth = {
      user: { role: 'user' },
      appSettings: { market_only_mode: true },
      ready: true,
      appSettingsReady: true,
    };
    renderWithProviders(<AppRoutes />, { route: '/portfolio' });
    expect(screen.getByText('Market page')).toBeInTheDocument();
    expect(screen.queryByText('Portfolio page')).toBeNull();
  });

  it('allows admin users when market-only mode is enabled', () => {
    mockedAuth = {
      user: { role: 'admin' },
      appSettings: { market_only_mode: true },
      ready: true,
      appSettingsReady: true,
    };
    renderWithProviders(<AppRoutes />, { route: '/portfolio' });
    expect(screen.getByText('Portfolio page')).toBeInTheDocument();
  });

  it('blocks section when market-only is disabled but section flag is off', () => {
    mockedAuth = {
      user: { role: 'user' },
      appSettings: { market_only_mode: false, portfolio_enabled: false },
      ready: true,
      appSettingsReady: true,
    };
    renderWithProviders(<AppRoutes />, { route: '/portfolio' });
    expect(screen.getByText('Market page')).toBeInTheDocument();
    expect(screen.queryByText('Portfolio page')).toBeNull();
  });

  it('allows section when market-only is disabled and section flag is on', () => {
    mockedAuth = {
      user: { role: 'user' },
      appSettings: { market_only_mode: false, portfolio_enabled: true },
      ready: true,
      appSettingsReady: true,
    };
    renderWithProviders(<AppRoutes />, { route: '/portfolio' });
    expect(screen.getByText('Portfolio page')).toBeInTheDocument();
  });
});
