/**
 * Tests for the RecentExplanationsPanel.
 *
 * The panel is the operator's at-a-glance feed of the most recent
 * AutoOps explanations, polled every 30 s. It must:
 *
 *   - render nothing for non-admins (defense in depth)
 *   - call `listExplanations({ limit: 10 })` on mount
 *   - render one row per item with a preview and an "Open" affordance
 *   - render a distinct empty state when zero rows come back
 *   - render a distinct error state when the request fails
 *   - flag fallback rows with a degraded badge (inline, not buried)
 *   - open the drawer when "Open" is clicked, in `existing` mode
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen, cleanup, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import type {
  AutoOpsExplanation,
  AutoOpsExplanationList,
} from '@/services/autoOps';

const listExplanations = vi.fn();
const explainDimension = vi.fn();

vi.mock('@/services/autoOps', () => ({
  listExplanations: (args: unknown) => listExplanations(args),
  explainDimension: (args: unknown) => explainDimension(args),
}));

let mockedRole: string | undefined = 'admin';
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    user: mockedRole ? { id: 1, role: mockedRole } : null,
    ready: true,
  }),
}));

import { RecentExplanationsPanel } from '../RecentExplanationsPanel';

const ROW_OK: AutoOpsExplanation = {
  id: 1,
  schema_version: 'v1',
  anomaly_id: 'coverage:stale_daily:2026-04-19',
  category: 'coverage',
  severity: 'critical',
  title: 'Daily coverage low',
  summary: 'Only 89% of tracked symbols have a fresh daily bar.',
  confidence: 'high',
  is_fallback: false,
  model: 'gpt-4o-mini',
  generated_at: '2026-04-19T13:30:00Z',
  payload: {
    narrative: 'Daily coverage dropped below the 95% SLO this morning.',
    is_fallback: false,
  },
};

const ROW_DEGRADED: AutoOpsExplanation = {
  ...ROW_OK,
  id: 2,
  category: 'jobs',
  severity: 'warning',
  is_fallback: true,
  payload: {
    narrative:
      'Two scheduled jobs failed in the last hour. LLM unavailable; using fallback runbook.',
    is_fallback: true,
  },
};

function asList(items: AutoOpsExplanation[], total?: number): AutoOpsExplanationList {
  return { total: total ?? items.length, items };
}

beforeEach(() => {
  mockedRole = 'admin';
  listExplanations.mockReset();
  explainDimension.mockReset();
});

afterEach(() => cleanup());

describe('<RecentExplanationsPanel />', () => {
  it('renders nothing when the user is not a platform admin', () => {
    mockedRole = 'analyst';
    renderWithProviders(<RecentExplanationsPanel />);
    expect(screen.queryByTestId('recent-explanations-panel')).toBeNull();
    expect(listExplanations).not.toHaveBeenCalled();
  });

  it('shows the loading skeleton, then the rows', async () => {
    listExplanations.mockResolvedValue(asList([ROW_OK, ROW_DEGRADED]));

    renderWithProviders(<RecentExplanationsPanel />);
    expect(
      screen.getByTestId('recent-explanations-skeleton'),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(listExplanations).toHaveBeenCalledTimes(1);
    });
    expect(listExplanations).toHaveBeenCalledWith({ limit: 10 });

    await waitFor(() => {
      expect(screen.getAllByTestId('recent-explanation-row')).toHaveLength(2);
    });

    // Degraded row gets a flag; healthy row does not.
    expect(screen.getAllByTestId('row-degraded-badge')).toHaveLength(1);

    // Preview text is truncated/normalised, not raw markdown.
    const previews = screen.getAllByTestId('recent-explanation-preview');
    expect(previews[0].textContent).toContain('Daily coverage dropped');
  });

  it('renders the empty state when zero explanations exist', async () => {
    listExplanations.mockResolvedValue(asList([], 0));

    renderWithProviders(<RecentExplanationsPanel />);

    await waitFor(() => {
      expect(
        screen.getByTestId('recent-explanations-empty'),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Click "Explain" on a dimension card/i),
    ).toBeInTheDocument();
  });

  it('renders an actionable error state when the feed fails', async () => {
    listExplanations.mockRejectedValue(new Error('boom'));

    renderWithProviders(<RecentExplanationsPanel />);

    await waitFor(() => {
      expect(
        screen.getByText(/Couldn't load recent explanations/i),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole('button', { name: /try again/i }),
    ).toBeInTheDocument();
  });

  it('opens the drawer in existing mode when a row is opened', async () => {
    listExplanations.mockResolvedValue(asList([ROW_OK]));

    renderWithProviders(<RecentExplanationsPanel />);

    const openBtn = await screen.findByRole('button', {
      name: /open explanation for coverage/i,
    });
    await userEvent.click(openBtn);

    await waitFor(() => {
      expect(screen.getByTestId('drawer-body')).toBeInTheDocument();
    });
    // Existing mode never round-trips to the explainer.
    expect(explainDimension).not.toHaveBeenCalled();
  });
});
