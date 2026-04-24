import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import Regime from '../Regime';

type Scenario = 'loading' | 'error' | 'empty' | 'data';

const { getCurrentRegime, getRegimeHistoryMock, apiGet, scenarioRef } = vi.hoisted(() => {
  const scenarioRef = { mode: 'data' as Scenario };

  const getCurrentRegime = vi.fn(() =>
    Promise.resolve({
      regime_state: 'R2',
      composite_score: 2.1,
      as_of_date: '2026-04-21',
      vix_spot: 14.1,
      vix3m_vix_ratio: 1.1,
      vvix_vix_ratio: 6.4,
      nh_nl: 45,
      pct_above_200d: 72,
      pct_above_50d: 68,
      score_vix: 2.0,
      score_vix3m_vix: 2.0,
      score_vvix_vix: 2.0,
      score_nh_nl: 2.0,
      score_above_200d: 2.0,
      score_above_50d: 2.0,
      weights_used: [1, 1, 1, 1, 1, 1],
      cash_floor_pct: 20,
      max_equity_exposure_pct: 100,
      regime_multiplier: 1,
    }),
  );

  const getRegimeHistoryMock = vi.fn(() => {
    if (scenarioRef.mode === 'error') {
      return Promise.reject(new Error('boom'));
    }
    if (scenarioRef.mode === 'loading') {
      return new Promise(() => {
        /* never resolves */
      });
    }
    if (scenarioRef.mode === 'empty') {
      return Promise.resolve({
        data: { history: [] },
      });
    }
    return Promise.resolve({
      data: {
        history: [
          { as_of_date: '2026-04-19', regime_state: 'R2', composite_score: 2.0 },
          { as_of_date: '2026-04-20', regime_state: 'R2', composite_score: 2.1 },
          { as_of_date: '2026-04-21', regime_state: 'R2', composite_score: 2.1 },
        ],
      },
    });
  });

  const apiGet = vi.fn((url: string) => {
    if (url.startsWith('/market-data/regime/history')) {
      return getRegimeHistoryMock();
    }
    return Promise.resolve({ data: {} });
  });

  return { getCurrentRegime, getRegimeHistoryMock, apiGet, scenarioRef };
});

vi.mock('@/services/api', () => ({
  default: { get: apiGet },
  marketDataApi: {
    getCurrentRegime,
  },
}));

// RegimeBanner imports from relative paths — mock the absolute-path services/api
// above; the banner itself uses useRegime → marketDataApi.getCurrentRegime.
vi.mock('../../../services/api', () => ({
  default: { get: apiGet },
  marketDataApi: {
    getCurrentRegime,
  },
}));

describe('signals/Regime', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiGet.mockClear();
    getCurrentRegime.mockClear();
    getRegimeHistoryMock.mockClear();
    cleanup();
  });

  it('renders history loading skeletons while the request is pending', () => {
    scenarioRef.mode = 'loading';
    renderWithProviders(<Regime />);
    expect(screen.getByTestId('regime-history-loading')).toBeInTheDocument();
  });

  it('renders an error card with retry when history fails', async () => {
    scenarioRef.mode = 'error';
    renderWithProviders(<Regime />);
    await waitFor(() => {
      expect(screen.getByTestId('regime-history-error')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('renders history rows when data is present', async () => {
    scenarioRef.mode = 'data';
    renderWithProviders(<Regime />);
    await waitFor(() => {
      expect(screen.getByTestId('regime-history-list')).toBeInTheDocument();
    });
    const r2Labels = await screen.findAllByText('R2');
    expect(r2Labels.length).toBeGreaterThanOrEqual(1);
  });
});
