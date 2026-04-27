import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { cleanup, screen } from '@testing-library/react';

import { renderWithProviders } from '../../../test/render';
import DisciplineTrajectoryTile from '../DisciplineTrajectoryTile';

const mockUseDisciplineTrajectory = vi.fn();

vi.mock('../../../hooks/useDisciplineTrajectory', () => ({
  useDisciplineTrajectory: (args: unknown) => mockUseDisciplineTrajectory(args),
}));

vi.mock('../../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({ currency: 'USD' }),
}));

describe('DisciplineTrajectoryTile', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders loading skeleton', () => {
    mockUseDisciplineTrajectory.mockReturnValue({
      isPending: true,
      isError: false,
      data: undefined,
      refetch: vi.fn(),
    });
    renderWithProviders(<DisciplineTrajectoryTile />);
    expect(document.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('renders error with retry', () => {
    mockUseDisciplineTrajectory.mockReturnValue({
      isPending: false,
      isError: true,
      data: undefined,
      refetch: vi.fn(),
    });
    renderWithProviders(<DisciplineTrajectoryTile />);
    expect(screen.getByText(/Discipline trajectory unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('renders empty state when starting equity is missing', () => {
    mockUseDisciplineTrajectory.mockReturnValue({
      isPending: false,
      isError: false,
      data: {
        account_id: '1',
        aggregate: false,
        starting_equity: null,
        current_equity: 0,
        anchors: null,
        projected_year_end: null,
        trend: 'flat',
        as_of: '2026-04-22T12:00:00Z',
        by_account: null,
      },
      refetch: vi.fn(),
    });
    renderWithProviders(<DisciplineTrajectoryTile />);
    expect(screen.getByText(/YTD starting equity is not available yet/i)).toBeInTheDocument();
  });

  it('renders data state with band labels', () => {
    mockUseDisciplineTrajectory.mockReturnValue({
      isPending: false,
      isError: false,
      data: {
        account_id: '1',
        aggregate: false,
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
        by_account: null,
      },
      refetch: vi.fn(),
    });
    renderWithProviders(<DisciplineTrajectoryTile />);
    expect(screen.getByText(/Discipline-bounded trajectory/i)).toBeInTheDocument();
    expect(screen.getByText(/Discipline bands \(D119 proportional\)/i)).toBeInTheDocument();
    expect(screen.getByText(/\$100,000/)).toBeInTheDocument();
    expect(screen.getByText(/\$110,000/)).toBeInTheDocument();
  });
});
