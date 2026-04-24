import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { cleanup, screen, fireEvent } from '@testing-library/react';

import { renderWithProviders } from '../../../test/render';
import DisciplineTrajectoryMultiAccount from '../DisciplineTrajectoryMultiAccount';

const mockUseDisciplineTrajectory = vi.fn();

vi.mock('../../../hooks/useDisciplineTrajectory', () => ({
  useDisciplineTrajectory: () => mockUseDisciplineTrajectory(),
}));

vi.mock('../../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({ currency: 'USD' }),
}));

describe('DisciplineTrajectoryMultiAccount', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('expands per-account rows', () => {
    mockUseDisciplineTrajectory.mockReturnValue({
      isPending: false,
      isError: false,
      data: {
        account_id: null,
        aggregate: true,
        starting_equity: 100_000,
        current_equity: 110_000,
        anchors: {
          unleveraged_ceiling: 150_000,
          leveraged_ceiling: 200_000,
          speculative_ceiling: 300_000,
        },
        projected_year_end: 165_000,
        trend: 'up',
        as_of: '2026-04-22T12:00:00Z',
        by_account: [
          {
            account_id: '10',
            broker: 'ibkr',
            account_number_suffix: '1111',
            starting_equity: 60_000,
            current_equity: 66_000,
          },
          {
            account_id: '11',
            broker: 'schwab',
            account_number_suffix: '2222',
            starting_equity: 40_000,
            current_equity: 44_000,
          },
        ],
      },
      refetch: vi.fn(),
    });
    renderWithProviders(<DisciplineTrajectoryMultiAccount />);
    expect(screen.getByText(/Consolidated discipline trajectory/i)).toBeInTheDocument();
    const toggle = screen.getByRole('button', { name: /Per-account positions on band scale/i });
    fireEvent.click(toggle);
    expect(screen.getByText(/IBKR ···1111/i)).toBeInTheDocument();
    expect(screen.getByText(/SCHWAB ···2222/i)).toBeInTheDocument();
  });
});
