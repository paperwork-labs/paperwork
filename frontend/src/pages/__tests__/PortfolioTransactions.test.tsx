import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen, waitFor } from '@/test/testing-library';
import { renderWithProviders } from '../../test/render';
import PortfolioTransactions from '../portfolio/PortfolioTransactions';

vi.mock('../../context/AccountContext', () => ({
  useAccountContext: () => ({ selected: 'all', setSelected: () => {} }),
}));

const mockUseActivity = vi.fn(() => ({
  data: { activity: [], total: 75 },
  isLoading: false,
}));

vi.mock('../../hooks/usePortfolio', () => ({
  useActivity: () => mockUseActivity(),
  usePortfolioAccounts: () => ({ data: [], isLoading: false }),
  usePortfolioSync: () => ({ mutate: () => {} }),
}));

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({ currency: 'USD' }),
}));

describe('PortfolioTransactions', () => {
  it('renders pagination with total from API', async () => {
    renderWithProviders(<PortfolioTransactions />, { route: '/portfolio/transactions' });
    await waitFor(() => {
      expect(screen.getByText(/1–50 of 75/)).toBeInTheDocument();
    });
  });

  it('shows table skeleton when activity is loading', async () => {
    mockUseActivity.mockReturnValueOnce({
      data: { activity: [], total: 0 },
      isLoading: true,
    });
    renderWithProviders(<PortfolioTransactions />, { route: '/portfolio/transactions' });
    await waitFor(() => {
      expect(screen.getByTestId('table-skeleton')).toBeInTheDocument();
    });
  });
});
