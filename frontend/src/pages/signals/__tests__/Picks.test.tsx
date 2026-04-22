import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import Picks from '../Picks';

type Scenario = 'loading' | 'error' | 'preview' | 'full' | 'empty';

const { get, scenarioRef } = vi.hoisted(() => {
  const scenarioRef = { mode: 'preview' as Scenario };
  const get = vi.fn(() => {
    if (scenarioRef.mode === 'loading') {
      return new Promise(() => {
        /* never resolves */
      });
    }
    if (scenarioRef.mode === 'error') {
      return Promise.reject(new Error('boom'));
    }
    if (scenarioRef.mode === 'empty') {
      return Promise.resolve({
        data: { is_preview: false, items: [] },
      });
    }
    if (scenarioRef.mode === 'preview') {
      return Promise.resolve({
        data: {
          is_preview: true,
          items: [
            {
              id: 1,
              ticker: 'AAPL',
              action: 'BUY',
              thesis: 'x',
              target_price: null,
              stop_loss: null,
              source: 'g',
              published_at: null,
            },
          ],
        },
      });
    }
    return Promise.resolve({
      data: {
        is_preview: false,
        items: [
          {
            id: 10,
            ticker: 'ZZZ',
            action: 'BUY',
            thesis: 't1',
            target_price: null,
            stop_loss: null,
            source: 's1',
            published_at: null,
          },
          {
            id: 11,
            ticker: 'QQQ',
            action: 'HOLD',
            thesis: 't2',
            target_price: null,
            stop_loss: null,
            source: 's2',
            published_at: null,
          },
        ],
      },
    });
  });
  return { get, scenarioRef };
});

vi.mock('@/services/api', () => ({
  default: { get },
}));

describe('signals/Picks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    get.mockClear();
    cleanup();
  });

  it('shows loading skeletons while the request is pending', () => {
    scenarioRef.mode = 'loading';
    renderWithProviders(<Picks />);
    expect(screen.getByTestId('picks-loading')).toBeInTheDocument();
  });

  it('shows an error card with retry when the request fails', async () => {
    scenarioRef.mode = 'error';
    renderWithProviders(<Picks />);
    await waitFor(() => {
      expect(screen.getByTestId('picks-error')).toBeInTheDocument();
    });
  });

  it('shows the empty state with a browse-strategies link when no picks exist', async () => {
    scenarioRef.mode = 'empty';
    renderWithProviders(<Picks />);
    await waitFor(() => {
      expect(screen.getByTestId('picks-empty')).toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: /browse strategies/i })).toHaveAttribute(
      'href',
      '/lab/strategies',
    );
  });

  it('shows preview banner routing to /pricing when API returns is_preview', async () => {
    scenarioRef.mode = 'preview';
    renderWithProviders(<Picks />);
    await waitFor(() => {
      expect(screen.getByText(/Upgrade to Lite to see all picks/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: /see plans/i })).toHaveAttribute(
      'href',
      '/pricing',
    );
  });

  it('shows full list without preview banner for lite response', async () => {
    scenarioRef.mode = 'full';
    renderWithProviders(<Picks />);
    await waitFor(() => {
      expect(screen.queryByText(/Upgrade to Lite to see all picks/i)).not.toBeInTheDocument();
    });
    expect(await screen.findByText('ZZZ')).toBeInTheDocument();
    expect(screen.getByText('QQQ')).toBeInTheDocument();
  });
});
