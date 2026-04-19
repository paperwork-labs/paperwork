import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import Picks from '../Picks';

const { get, scenarioRef } = vi.hoisted(() => {
  const scenarioRef = { mode: 'preview' as 'preview' | 'full' };
  const get = vi.fn(() => {
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

describe('Picks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    get.mockClear();
    cleanup();
  });

  it('shows preview banner when API returns is_preview', async () => {
    scenarioRef.mode = 'preview';
    renderWithProviders(<Picks />);
    await waitFor(() => {
      expect(screen.getByText(/Upgrade to Lite to see all picks/i)).toBeInTheDocument();
    });
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
