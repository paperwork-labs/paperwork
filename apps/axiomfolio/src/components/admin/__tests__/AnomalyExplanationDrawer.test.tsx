/**
 * Tests for the AutoOps AnomalyExplanationDrawer.
 *
 * The drawer is the operator-facing surface for one anomaly explanation,
 * so the contract we lock down here mirrors what an SRE would expect
 * when they click "Explain" on a degraded dimension card:
 *
 *   - it does NOT render for non-admins (defense in depth)
 *   - dimension mode POSTs to `/admin/agent/explain/dimension` exactly
 *     once per open and renders the resulting payload
 *   - existing mode skips the network call and renders the supplied
 *     explanation directly
 *   - the degraded badge appears iff `is_fallback === true`
 *   - the error state surfaces a retry that reissues the same request
 *   - loading / error / empty / data are all distinct states (per
 *     `.cursor/rules/no-silent-fallback.mdc`)
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen, cleanup, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import type { AutoOpsExplanation } from '@/services/autoOps';

const explainDimension = vi.fn();

vi.mock('@/services/autoOps', () => ({
  explainDimension: (args: unknown) => explainDimension(args),
  listExplanations: vi.fn(),
}));

let mockedRole: string | undefined = 'admin';
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    user: mockedRole ? { id: 1, role: mockedRole } : null,
    ready: true,
  }),
}));

import { AnomalyExplanationDrawer } from '../AnomalyExplanationDrawer';

const SAMPLE_EXPLANATION: AutoOpsExplanation = {
  id: 42,
  schema_version: 'v1',
  anomaly_id: 'coverage:stale_daily:2026-04-19',
  category: 'coverage',
  severity: 'critical',
  title: 'Daily coverage is below 95%',
  summary: 'Only 89.2% of tracked symbols have a fresh daily bar.',
  confidence: 'high',
  is_fallback: false,
  model: 'gpt-4o-mini',
  generated_at: '2026-04-19T13:30:00Z',
  payload: {
    schema_version: 'v1',
    anomaly_id: 'coverage:stale_daily:2026-04-19',
    title: 'Daily coverage is below 95%',
    summary: 'Only 89.2% of tracked symbols have a fresh daily bar.',
    narrative:
      '## Why this fired\n\nDaily coverage dropped to **89.2%**, below the 95% SLO.',
    root_cause_hypothesis: 'Yahoo provider rate limited overnight.',
    steps: [
      {
        order: 1,
        description: 'Backfill stale daily bars from Polygon.',
        runbook_section: '#troubleshooting',
        proposed_task: 'admin_market_backfill_daily_tracked',
        requires_approval: false,
        rationale: 'Polygon has uncapped daily bar history.',
      },
      {
        order: 2,
        description: 'Re-run indicator recompute after backfill.',
        runbook_section: '#troubleshooting',
        proposed_task: 'admin_indicators_recompute_universe',
        requires_approval: true,
        rationale: null,
      },
    ],
    confidence: 'high',
    runbook_excerpts: ['#troubleshooting'],
    generated_at: '2026-04-19T13:30:00Z',
    model: 'gpt-4o-mini',
    is_fallback: false,
  },
};

beforeEach(() => {
  mockedRole = 'admin';
  explainDimension.mockReset();
});

afterEach(() => cleanup());

describe('<AnomalyExplanationDrawer />', () => {
  it('renders nothing when the user is not a platform admin', () => {
    mockedRole = 'analyst';
    renderWithProviders(
      <AnomalyExplanationDrawer
        open
        onOpenChange={() => {}}
        trigger={{ mode: 'existing', explanation: SAMPLE_EXPLANATION }}
      />,
    );
    expect(screen.queryByTestId('anomaly-explanation-drawer')).toBeNull();
  });

  it('renders an existing explanation without firing a request', () => {
    renderWithProviders(
      <AnomalyExplanationDrawer
        open
        onOpenChange={() => {}}
        trigger={{ mode: 'existing', explanation: SAMPLE_EXPLANATION }}
      />,
    );

    expect(screen.getByTestId('anomaly-explanation-drawer')).toBeInTheDocument();
    expect(screen.getByText('Daily coverage is below 95%')).toBeInTheDocument();
    expect(
      screen.getByText(/Yahoo provider rate limited overnight/),
    ).toBeInTheDocument();
    const steps = screen.getAllByTestId('explanation-step');
    expect(steps).toHaveLength(2);
    expect(explainDimension).not.toHaveBeenCalled();
  });

  it('shows the degraded badge when the explanation is a fallback', () => {
    const fallback: AutoOpsExplanation = {
      ...SAMPLE_EXPLANATION,
      is_fallback: true,
      payload: { ...SAMPLE_EXPLANATION.payload, is_fallback: true },
    };
    renderWithProviders(
      <AnomalyExplanationDrawer
        open
        onOpenChange={() => {}}
        trigger={{ mode: 'existing', explanation: fallback }}
      />,
    );
    expect(screen.getByTestId('degraded-badge')).toBeInTheDocument();
  });

  it('hides the degraded badge for healthy LLM-generated explanations', () => {
    renderWithProviders(
      <AnomalyExplanationDrawer
        open
        onOpenChange={() => {}}
        trigger={{ mode: 'existing', explanation: SAMPLE_EXPLANATION }}
      />,
    );
    expect(screen.queryByTestId('degraded-badge')).toBeNull();
  });

  it('issues a POST and renders the response in dimension mode', async () => {
    explainDimension.mockResolvedValue(SAMPLE_EXPLANATION);

    renderWithProviders(
      <AnomalyExplanationDrawer
        open
        onOpenChange={() => {}}
        trigger={{
          mode: 'dimension',
          dimension: 'coverage',
          dimensionPayload: { status: 'red', stale_daily: 27 },
        }}
      />,
    );

    expect(screen.getByTestId('drawer-skeleton')).toBeInTheDocument();

    await waitFor(() => {
      expect(explainDimension).toHaveBeenCalledTimes(1);
    });
    expect(explainDimension).toHaveBeenCalledWith({
      dimension: 'coverage',
      dimensionPayload: { status: 'red', stale_daily: 27 },
    });

    await waitFor(() => {
      expect(screen.getByTestId('drawer-body')).toBeInTheDocument();
    });
    expect(screen.getByText('Daily coverage is below 95%')).toBeInTheDocument();
  });

  it('shows an error state with retry when the request fails', async () => {
    explainDimension
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce(SAMPLE_EXPLANATION);

    renderWithProviders(
      <AnomalyExplanationDrawer
        open
        onOpenChange={() => {}}
        trigger={{
          mode: 'dimension',
          dimension: 'coverage',
          dimensionPayload: { status: 'red' },
        }}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Couldn't generate explanation/i),
      ).toBeInTheDocument();
    });

    const retry = screen.getByRole('button', { name: /try again/i });
    await userEvent.click(retry);

    await waitFor(() => {
      expect(explainDimension).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(screen.getByTestId('drawer-body')).toBeInTheDocument();
    });
  });
});
