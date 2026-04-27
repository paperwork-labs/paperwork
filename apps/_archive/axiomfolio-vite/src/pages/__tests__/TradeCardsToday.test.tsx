import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import TradeCardsToday from '../TradeCardsToday';

type Scenario = 'loading' | 'error' | 'empty' | 'data';

const { get, scenarioRef } = vi.hoisted(() => {
  const scenarioRef = { mode: 'data' as Scenario };
  const sampleCard = {
    rank: 1,
    candidate_id: 42,
    generated_at: new Date().toISOString(),
    action: 'BUY',
    underlying: {
      symbol: 'ACME',
      name: 'Acme Corp',
      sector: 'Technology',
      stage_label: '2A',
      current_price: '100.25',
      rs_mansfield_pct: '88.10',
      perf_5d: '3.40',
      td_buy_setup: 7,
      td_sell_setup: 0,
      next_earnings: null,
      days_to_earnings: null,
      atr_14: '2.50',
      atrp_14: '2.49',
      sma_21: '97.10',
      volume_avg_20d: '500000',
    },
    regime: {
      regime_state: 'R1',
      composite_score: '2.0',
      regime_multiplier: '1.00',
      as_of_date: null,
    },
    score: {
      pick_quality_score: '72.50',
      regime_multiplier: '1.00',
      components: {},
    },
    contract_status: 'ready',
    contract: {
      contract_type: 'call_debit',
      occ_symbol: 'ACME240101C00100000',
      expiry: new Date(Date.now() + 30 * 86400_000).toISOString().slice(0, 10),
      strike: '100',
      bid: '3.45',
      mid: '3.50',
      ask: '3.55',
      spread_pct: '2.85',
      delta: '0.55',
      open_interest: 1200,
      volume: 300,
    },
    limit_tiers: [
      {
        tier: 'passive',
        price: '3.47',
        logic: 'Just above bid',
        fill_likelihood: 'low',
      },
      {
        tier: 'mid',
        price: '3.50',
        logic: 'Midpoint',
        fill_likelihood: 'moderate',
      },
      {
        tier: 'aggressive',
        price: '3.54',
        logic: 'Near ask',
        fill_likelihood: "don't",
      },
    ],
    sizing_status: 'computed',
    sizing: {
      tier: 'T2',
      contracts: 3,
      shares: 0,
      premium_dollars: '1050.00',
      premium_pct_of_account: '1.05',
      full_position_dollars: '100000.00',
      capped_position_dollars: '75000.00',
      stage_cap: '0.75',
      regime_multiplier: '1.00',
      account_size: '100000.00',
      risk_budget: '1000.00',
    },
    stops: {
      premium_stop: '1.75',
      underlying_stop: '97.10',
      underlying_stop_reason: 'Close below SMA21 = thesis invalidated',
      calendar_stop: null,
      calendar_stop_reason: null,
    },
    alerts: [
      {
        alert_type: 'profit_target',
        level: 'info',
        message: 'Scale half at +75% premium; trail the remainder on SMA21.',
      },
    ],
    anti_thesis: 'Close below SMA21 invalidates the setup',
    notes: [],
  };

  const get = vi.fn(() => {
    switch (scenarioRef.mode) {
      case 'loading':
        return new Promise(() => {
          /* never resolves */
        });
      case 'error':
        return Promise.reject(new Error('boom'));
      case 'empty':
        return Promise.resolve({
          data: {
            items: [],
            errors: [],
            total: 0,
            limit: 20,
            offset: 0,
            user_id: 1,
          },
        });
      default:
        return Promise.resolve({
          data: {
            items: [sampleCard],
            errors: [],
            total: 1,
            limit: 20,
            offset: 0,
            user_id: 1,
          },
        });
    }
  });
  return { get, scenarioRef };
});

vi.mock('@/services/api', () => ({
  default: { get },
}));

describe('TradeCardsToday', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    get.mockClear();
    cleanup();
  });

  it('renders a loading skeleton while the request is pending', () => {
    scenarioRef.mode = 'loading';
    renderWithProviders(<TradeCardsToday />);
    expect(screen.getByTestId('trade-cards-loading')).toBeInTheDocument();
  });

  it('shows an error state when the API fails', async () => {
    scenarioRef.mode = 'error';
    renderWithProviders(<TradeCardsToday />);
    await waitFor(() => {
      expect(screen.getByTestId('trade-cards-error')).toBeInTheDocument();
    });
    expect(screen.getByText(/Unable to load trade cards/i)).toBeInTheDocument();
  });

  it('shows the empty state when no cards are returned', async () => {
    scenarioRef.mode = 'empty';
    renderWithProviders(<TradeCardsToday />);
    await waitFor(() => {
      expect(screen.getByTestId('trade-cards-empty')).toBeInTheDocument();
    });
    expect(
      screen.getByText(/No trade cards today — the market did not hand us a plan worth printing/i),
    ).toBeInTheDocument();
  });

  it('renders a card with sizing, contract and limit tiers in the data state', async () => {
    scenarioRef.mode = 'data';
    renderWithProviders(<TradeCardsToday />);
    await waitFor(() => {
      expect(screen.getByTestId('trade-cards-data')).toBeInTheDocument();
    });
    expect(screen.getByTestId('trade-card-42')).toBeInTheDocument();
    expect(screen.getByText('ACME')).toBeInTheDocument();
    expect(screen.getByText(/ACME240101C00100000/)).toBeInTheDocument();
    expect(screen.getByTestId('limit-passive')).toBeInTheDocument();
    expect(screen.getByTestId('limit-mid')).toBeInTheDocument();
    expect(screen.getByTestId('limit-aggressive')).toBeInTheDocument();
    expect(screen.getByText(/Scale half at \+75% premium/i)).toBeInTheDocument();
  });
});
