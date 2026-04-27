import React from 'react';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@testing-library/react';

import { renderWithProviders } from '../../../test/render';
import { IncomeCalendar, type IncomeCalendarResponse } from '../IncomeCalendar';

const mockGetIncomeCalendar = vi.fn();

vi.mock('../../../services/api', () => ({
  portfolioApi: {
    getIncomeCalendar: (...args: unknown[]) => mockGetIncomeCalendar(...args),
  },
}));

vi.mock('../../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    currency: 'USD',
    timezone: 'America/New_York',
    tableDensity: 'comfortable',
    coverageHistogramWindowDays: null,
    colorPalette: 'default',
  }),
}));

function fakePastResponse(): IncomeCalendarResponse {
  // One cell with two symbols, so we can also assert per-symbol breakdown ordering.
  return {
    mode: 'past',
    months: 12,
    tax_data_available: true,
    cells: [
      {
        date: '2026-04-15',
        total: 61.5,
        tax_withheld: 2.4,
        by_symbol: [
          { symbol: 'MSFT', amount: 37.5 },
          { symbol: 'AAPL', amount: 24.0 },
        ],
      },
    ],
    monthly_totals: [
      { month: '2025-05', total: 0, tax_withheld: 0, projected: false },
      { month: '2025-06', total: 0, tax_withheld: 0, projected: false },
      { month: '2025-07', total: 0, tax_withheld: 0, projected: false },
      { month: '2025-08', total: 0, tax_withheld: 0, projected: false },
      { month: '2025-09', total: 0, tax_withheld: 0, projected: false },
      { month: '2025-10', total: 0, tax_withheld: 0, projected: false },
      { month: '2025-11', total: 0, tax_withheld: 0, projected: false },
      { month: '2025-12', total: 0, tax_withheld: 0, projected: false },
      { month: '2026-01', total: 0, tax_withheld: 0, projected: false },
      { month: '2026-02', total: 0, tax_withheld: 0, projected: false },
      { month: '2026-03', total: 0, tax_withheld: 0, projected: false },
      { month: '2026-04', total: 61.5, tax_withheld: 2.4, projected: false },
    ],
    generated_at: '2026-04-19T12:00:00+00:00',
  };
}

function fakeEmptyResponse(): IncomeCalendarResponse {
  return {
    mode: 'past',
    months: 12,
    tax_data_available: false,
    cells: [],
    monthly_totals: Array.from({ length: 12 }, (_, i) => ({
      month: `2025-${String(i + 1).padStart(2, '0')}`,
      total: 0,
      tax_withheld: 0,
      projected: false,
    })),
    generated_at: '2026-04-19T12:00:00+00:00',
  };
}

describe('IncomeCalendar', () => {
  beforeEach(() => {
    mockGetIncomeCalendar.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders the loading skeleton before data arrives', () => {
    let resolve: (v: IncomeCalendarResponse) => void;
    mockGetIncomeCalendar.mockImplementation(
      () => new Promise<IncomeCalendarResponse>((r) => { resolve = r; }),
    );
    renderWithProviders(<IncomeCalendar />);
    // Mode selector is always present; the data grid should not be.
    expect(screen.getByLabelText(/Income calendar mode/i)).toBeInTheDocument();
    expect(
      screen.queryByRole('grid', { name: /Dividend income calendar/i }),
    ).toBeNull();
    // Resolve the in-flight promise so the test runner cleans up cleanly.
    resolve!(fakeEmptyResponse());
  });

  it('shows the empty-state copy when the payload contains no cells', async () => {
    mockGetIncomeCalendar.mockResolvedValue(fakeEmptyResponse());
    renderWithProviders(<IncomeCalendar />);
    expect(
      await screen.findByText(/Your income calendar is quiet — no pay dates on the books yet/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Add positions or import history and sync/i),
    ).toBeInTheDocument();
  });

  it('renders monthly totals and the annual total when the payload has data', async () => {
    mockGetIncomeCalendar.mockResolvedValue(fakePastResponse());
    renderWithProviders(<IncomeCalendar />);

    await waitFor(() => {
      expect(
        screen.getByRole('grid', { name: /Dividend income calendar/i }),
      ).toBeInTheDocument();
    });

    // The annual total ($62 at 0dp) and the April monthly total render
    // the same value, so we expect at least two nodes.
    expect(screen.getAllByText('$62').length).toBeGreaterThanOrEqual(2);
  });

  it('disables the Net toggle when tax data is unavailable', async () => {
    mockGetIncomeCalendar.mockResolvedValue(fakeEmptyResponse());
    renderWithProviders(<IncomeCalendar />);
    const toggle = await screen.findByRole('button', { name: /Gross/i });
    expect(toggle).toBeDisabled();
  });

  it('renders an error state with retry when the query fails', async () => {
    mockGetIncomeCalendar.mockRejectedValue(new Error('boom'));
    renderWithProviders(<IncomeCalendar />);
    expect(
      await screen.findByText(/We couldn't load your income calendar/i),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
  });
});
