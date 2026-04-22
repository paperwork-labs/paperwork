import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import Candidates from '../Candidates';

type Scenario = 'loading' | 'error' | 'empty' | 'data';

const { get, scenarioRef } = vi.hoisted(() => {
  const scenarioRef = { mode: 'data' as Scenario };
  const get = vi.fn(() => {
    if (scenarioRef.mode === 'error') {
      return Promise.reject(new Error('boom'));
    }
    if (scenarioRef.mode === 'loading') {
      return new Promise(() => {
        /* never resolves — stays in loading state */
      });
    }
    if (scenarioRef.mode === 'empty') {
      return Promise.resolve({
        data: { items: [], total: 0, limit: 50, offset: 0 },
      });
    }
    return Promise.resolve({
      data: {
        items: [
          {
            id: 1,
            ticker: 'NVDA',
            action: 'BUY',
            generator_name: 'momentum-v1',
            generator_version: '1',
            generator_score: '0.87',
            pick_quality_score: '8.4',
            score: {
              total_score: 8.4,
              components: { momentum: 0.9 },
              regime_multiplier: 1.0,
              computed_at: '2026-04-21T12:00:00Z',
            },
            thesis: 'Clean breakout over 20DMA on heavy volume.',
            signals: null,
            generated_at: '2026-04-21T12:00:00Z',
          },
          {
            id: 2,
            ticker: 'MSFT',
            action: 'WATCH',
            generator_name: 'mean-reversion-v2',
            generator_version: '2',
            generator_score: null,
            pick_quality_score: null,
            score: null,
            thesis: null,
            signals: null,
            generated_at: null,
          },
        ],
        total: 2,
        limit: 50,
        offset: 0,
      },
    });
  });
  return { get, scenarioRef };
});

vi.mock('@/services/api', () => ({
  default: { get },
}));

describe('signals/Candidates', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    get.mockClear();
    cleanup();
  });

  it('renders loading skeletons while the request is pending', () => {
    scenarioRef.mode = 'loading';
    renderWithProviders(<Candidates />);
    expect(screen.getByTestId('candidates-loading')).toBeInTheDocument();
  });

  it('renders an error card with retry when the request fails', async () => {
    scenarioRef.mode = 'error';
    renderWithProviders(<Candidates />);
    await waitFor(() => {
      expect(screen.getByTestId('candidates-error')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('renders the empty state with a CTA to strategies when no candidates exist', async () => {
    scenarioRef.mode = 'empty';
    renderWithProviders(<Candidates />);
    await waitFor(() => {
      expect(screen.getByTestId('candidates-empty')).toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: /browse strategies/i })).toHaveAttribute(
      'href',
      '/lab/strategies',
    );
  });

  it('renders candidate rows with ticker, action, and quality score when data is present', async () => {
    scenarioRef.mode = 'data';
    renderWithProviders(<Candidates />);
    expect(await screen.findByText('NVDA')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
    expect(screen.getByText(/Quality 8\.4/i)).toBeInTheDocument();
    expect(screen.getByText('BUY')).toBeInTheDocument();
    expect(screen.getByText('WATCH')).toBeInTheDocument();
  });
});
