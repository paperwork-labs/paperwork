import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { renderWithProviders } from '@/test/render';
import { MarketingHeader } from '../MarketingHeader';

function mockDesktop(): void {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

function mockMobile(): void {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe('MarketingHeader', () => {
  beforeEach(() => {
    mockDesktop();
  });

  it('wraps the logo in a home link to /', () => {
    renderWithProviders(<MarketingHeader />, { route: '/why-free' });
    const home = screen.getByRole('link', { name: 'AxiomFolio home' });
    expect(home).toHaveAttribute('href', '/');
  });

  it('renders all primary nav and CTA items on desktop', () => {
    renderWithProviders(<MarketingHeader />, { route: '/why-free' });
    expect(screen.getByRole('link', { name: 'Why free' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Pricing' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Register' })).toBeInTheDocument();
  });

  it('toggles the mobile menu disclosure on click', async () => {
    mockMobile();
    const user = userEvent.setup();
    renderWithProviders(<MarketingHeader />, { route: '/pricing' });

    const openBtn = screen.getByRole('button', { name: 'Open marketing menu' });
    expect(screen.queryByRole('link', { name: 'Why free' })).not.toBeInTheDocument();

    await user.click(openBtn);

    expect(screen.getByRole('link', { name: 'Why free' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Pricing' })).toBeInTheDocument();

    const closeBtn = screen.getByRole('button', { name: 'Close menu' });
    await user.click(closeBtn);
  });
});
