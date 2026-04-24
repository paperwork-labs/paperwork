import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '../../../test/render';
import { PositionSleeveToggle } from '../PositionSleeveToggle';

const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

const patchMock = vi.fn();

vi.mock('@/services/api', () => ({
  __esModule: true,
  default: {
    patch: (...args: unknown[]) => patchMock(...args),
  },
  handleApiError: (err: unknown) => {
    if (err && typeof err === 'object' && 'message' in err) {
      return String((err as { message?: string }).message ?? 'error');
    }
    return 'error';
  },
}));

describe('PositionSleeveToggle', () => {
  beforeEach(() => {
    patchMock.mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
  });

  it('renders both sleeve options and marks the current one pressed', () => {
    renderWithProviders(
      <PositionSleeveToggle
        positionId={1}
        symbol="AAPL"
        currentSleeve="active"
      />
    );
    const active = screen.getByRole('button', { name: /active/i });
    const conviction = screen.getByRole('button', { name: /conviction/i });
    expect(active).toHaveAttribute('aria-pressed', 'true');
    expect(conviction).toHaveAttribute('aria-pressed', 'false');
  });

  it('calls PATCH /positions/:id/sleeve and shows success toast', async () => {
    patchMock.mockResolvedValueOnce({
      data: { id: 42, symbol: 'NVDA', sleeve: 'conviction' },
    });

    renderWithProviders(
      <PositionSleeveToggle
        positionId={42}
        symbol="NVDA"
        currentSleeve="active"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /conviction/i }));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledWith('/positions/42/sleeve', {
        sleeve: 'conviction',
      });
    });

    await waitFor(() => {
      expect(toastSuccess).toHaveBeenCalled();
    });

    const conviction = screen.getByRole('button', { name: /conviction/i });
    expect(conviction).toHaveAttribute('aria-pressed', 'true');
  });

  it('rolls back optimistic state and shows error toast on failure', async () => {
    patchMock.mockRejectedValueOnce(new Error('500'));

    renderWithProviders(
      <PositionSleeveToggle
        positionId={7}
        symbol="AMZN"
        currentSleeve="active"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /conviction/i }));

    await waitFor(() => {
      expect(toastError).toHaveBeenCalled();
    });

    // Rolled back to original sleeve.
    const active = screen.getByRole('button', { name: /active/i });
    const conviction = screen.getByRole('button', { name: /conviction/i });
    expect(active).toHaveAttribute('aria-pressed', 'true');
    expect(conviction).toHaveAttribute('aria-pressed', 'false');
    const container = active.closest('[data-status]');
    expect(container?.getAttribute('data-status')).toBe('error');
  });

  it('does not fire a mutation when clicking the already-selected sleeve', () => {
    renderWithProviders(
      <PositionSleeveToggle
        positionId={3}
        symbol="GOOG"
        currentSleeve="conviction"
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /conviction/i }));
    expect(patchMock).not.toHaveBeenCalled();
  });
});
