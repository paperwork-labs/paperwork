import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { cleanup, screen, waitFor } from '@testing-library/react';

import { renderWithProviders } from '../../../test/render';
import type { TradeDecisionExplanation } from '../../../types/tradeDecision';

const mockGet = vi.fn();
const mockRegenerate = vi.fn();

vi.mock('../../../services/tradeDecision', () => ({
  tradeDecisionApi: {
    get: (orderId: number) => mockGet(orderId),
    regenerate: (orderId: number) => mockRegenerate(orderId),
  },
}));

import { ExplanationDrawer } from '../ExplanationDrawer';

const SAMPLE: TradeDecisionExplanation = {
  row_id: 1,
  order_id: 99,
  user_id: 7,
  version: 1,
  trigger_type: 'pick',
  schema_version: 'trade_decision.v1',
  model_used: 'stub',
  is_fallback: false,
  cost_usd: '0',
  prompt_token_count: 0,
  completion_token_count: 0,
  payload: {
    trigger: 'pick',
    headline: 'Bought AAPL on Stage 2A breakout',
    rationale_bullets: [
      'Stage 2A confirmed by SMA50 > SMA150 > SMA200.',
      'RSI 58, no overbought.',
    ],
    risk_context: {
      position_size_label: '~1.5% equity',
      stop_placement: 'ATR-based, ~7% below entry',
      regime_alignment: 'Aligned with R2 long bias',
    },
    outcome_so_far: {
      status: 'open',
      summary: 'Position currently +2.3% above entry.',
      pnl_label: '+2.3%',
    },
    narrative:
      'AAPL printed a Stage 2A confirmation and the regime supported long exposure.\n\nRisk was sized to ~1.5% of equity with an ATR-based stop.',
  },
  narrative:
    'AAPL printed a Stage 2A confirmation and the regime supported long exposure.\n\nRisk was sized to ~1.5% of equity with an ATR-based stop.',
  generated_at: '2026-04-19T12:00:00Z',
  reused: false,
};

describe('ExplanationDrawer', () => {
  afterEach(() => {
    cleanup();
    mockGet.mockReset();
    mockRegenerate.mockReset();
  });

  it('does not call the API when closed', () => {
    renderWithProviders(
      <ExplanationDrawer orderId={99} open={false} onOpenChange={() => undefined} />,
    );
    expect(mockGet).not.toHaveBeenCalled();
  });

  it('shows a loading state while the explanation is in flight', async () => {
    let resolve: (v: TradeDecisionExplanation) => void = () => undefined;
    mockGet.mockImplementation(
      () => new Promise<TradeDecisionExplanation>((r) => (resolve = r)),
    );
    renderWithProviders(
      <ExplanationDrawer orderId={99} open onOpenChange={() => undefined} />,
    );
    expect(await screen.findByTestId('explanation-loading')).toBeInTheDocument();
    resolve(SAMPLE);
    await waitFor(() =>
      expect(screen.queryByTestId('explanation-loading')).toBeNull(),
    );
  });

  it('renders headline, bullets, risk, outcome, and narrative when data resolves', async () => {
    mockGet.mockResolvedValue(SAMPLE);
    renderWithProviders(
      <ExplanationDrawer orderId={99} open onOpenChange={() => undefined} />,
    );
    expect(
      await screen.findByText('Bought AAPL on Stage 2A breakout'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Stage 2A confirmed by SMA50 > SMA150 > SMA200.'),
    ).toBeInTheDocument();
    expect(screen.getByText('~1.5% equity')).toBeInTheDocument();
    expect(screen.getByText('+2.3%')).toBeInTheDocument();
    // The narrative is split on blank lines into paragraphs.
    expect(
      screen.getByText(/AAPL printed a Stage 2A confirmation/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Risk was sized to ~1\.5% of equity/),
    ).toBeInTheDocument();
  });

  it('renders a degraded badge when is_fallback is true', async () => {
    mockGet.mockResolvedValue({ ...SAMPLE, is_fallback: true });
    renderWithProviders(
      <ExplanationDrawer orderId={99} open onOpenChange={() => undefined} />,
    );
    expect(await screen.findByText('Degraded')).toBeInTheDocument();
  });

  it('shows an error state with retry when the fetch fails', async () => {
    mockGet.mockRejectedValue(new Error('boom'));
    renderWithProviders(
      <ExplanationDrawer orderId={99} open onOpenChange={() => undefined} />,
    );
    expect(await screen.findByTestId('explanation-error')).toBeInTheDocument();
    expect(
      screen.getByText('Could not load this explanation.'),
    ).toBeInTheDocument();
  });
});
