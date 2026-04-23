import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, cleanup, screen, waitFor } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';

import PositionsTabShell from '../PositionsTabShell';

// Stub each tab body — we only care that the shell mounts the right one
// when the URL tab param changes. This keeps the test from pulling in
// ~3k lines of table code and its data hooks.
vi.mock('../PortfolioHoldings', () => ({
  __esModule: true,
  default: () => <div data-testid="tab-holdings">holdings body</div>,
}));
vi.mock('../PortfolioOptions', () => ({
  __esModule: true,
  default: () => <div data-testid="tab-options">options body</div>,
}));
vi.mock('../PortfolioCategories', () => ({
  __esModule: true,
  default: () => <div data-testid="tab-categories">categories body</div>,
}));

function renderShell(route: string = '/portfolio/positions') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <PositionsTabShell />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PositionsTabShell', () => {
  beforeEach(() => {
    // Silence react-router's useSearchParams replace warnings in tests.
  });
  afterEach(() => cleanup());

  it('renders Holdings by default', async () => {
    renderShell();
    await waitFor(() => {
      expect(screen.getByTestId('tab-holdings')).toBeInTheDocument();
    });
  });

  it('switches to Options when the Options tab is clicked', async () => {
    const user = userEvent.setup();
    renderShell();
    await waitFor(() => screen.getByTestId('tab-holdings'));
    await user.click(screen.getByRole('tab', { name: /Options/i }));
    await waitFor(() => {
      expect(screen.getByTestId('tab-options')).toBeInTheDocument();
    });
  });

  it('mounts the Categories tab (not Lots) when ?tab=categories is in the URL', async () => {
    renderShell('/portfolio/positions?tab=categories');
    await waitFor(() => {
      expect(screen.getByTestId('tab-categories')).toBeInTheDocument();
    });
  });

  it('exposes Categories in the tab strip and hides the old "Lots" label', async () => {
    renderShell();
    await waitFor(() => screen.getByTestId('tab-holdings'));
    expect(screen.getByRole('tab', { name: /Categories/i })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: /^Lots$/i })).toBeNull();
  });

  // Old bookmark preservation: `?tab=lots` predates the IA correction
  // (Tax Center moved to /portfolio/tax; Categories took its slot). Rewrite
  // the alias in place so the user lands on Categories, not a blank tab.
  it('redirects the legacy ?tab=lots bookmark to Categories', async () => {
    renderShell('/portfolio/positions?tab=lots');
    await waitFor(() => {
      expect(screen.getByTestId('tab-categories')).toBeInTheDocument();
    });
  });
});
