import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminHealthBanner from '../AdminHealthBanner';
import AdminDomainCards from '../AdminDomainCards';
import AdminRunbook from '../AdminRunbook';
import CoverageHealthStrip from '../../coverage/CoverageHealthStrip';
import type { AdminHealthResponse } from '../../../types/adminHealth';
import { renderWithProviders } from '../../../test/render';

vi.mock('../../../utils/format', () => ({
  formatDateTime: (v: string | undefined) => v || '—',
}));

afterEach(() => cleanup());

const MOCK_HEALTH: AdminHealthResponse = {
  composite_status: 'yellow',
  composite_reason: 'Degraded: jobs.',
  dimensions: {
    coverage: {
      status: 'green',
      daily_pct: 98.0,
      m5_pct: 90.0,
      stale_daily: 0,
      stale_m5: 0,
      tracked_count: 500,
      expected_date: '2026-01-08',
      summary: 'OK',
    },
    stage_quality: {
      status: 'green',
      unknown_rate: 0.1,
      invalid_count: 0,
      monotonicity_issues: 0,
      stale_stage_count: 0,
      total_symbols: 500,
      stage_counts: { '2A': 200 },
    },
    jobs: {
      status: 'red',
      window_hours: 24,
      total: 10,
      ok_count: 8,
      error_count: 2,
      running_count: 0,
      cancelled_count: 0,
      completed_count: 10,
      success_rate: 0.8,
      latest_failed: {
        id: 1,
        task_name: 'backfill_daily',
        status: 'error',
        started_at: '2026-01-08T00:00:00Z',
        error: 'timeout',
      },
    },
    audit: {
      status: 'green',
      tracked_total: 500,
      daily_fill_pct: 98.0,
      snapshot_fill_pct: 95.0,
      missing_sample: ['AAPL', 'MSFT'],
    },
  },
  task_runs: {},
  thresholds: {
    coverage_daily_pct_min: 95,
    coverage_stale_daily_max: 0,
    stage_unknown_rate_max: 0.35,
    stage_invalid_max: 0,
    stage_monotonicity_max: 0,
    jobs_error_max: 0,
    jobs_lookback_hours: 24,
    audit_daily_fill_pct_min: 95,
    audit_snapshot_fill_pct_min: 90,
  },
  checked_at: '2026-01-08T12:00:00Z',
};

describe('AdminHealthBanner', () => {
  it('renders composite status and reason', () => {
    renderWithProviders(<AdminHealthBanner health={MOCK_HEALTH} />);
    expect(screen.getByText('YELLOW')).toBeTruthy();
    expect(screen.getByText(/Degraded: jobs/)).toBeTruthy();
    expect(screen.getByText('System Health')).toBeTruthy();
  });

  it('renders nothing when health is null', () => {
    renderWithProviders(<AdminHealthBanner health={null} />);
    expect(screen.queryByText('System Health')).toBeNull();
  });

  it('renders per-dimension badges with colorPalette', () => {
    renderWithProviders(<AdminHealthBanner health={MOCK_HEALTH} />);
    expect(screen.getByText('coverage')).toBeTruthy();
    expect(screen.getByText('stage quality')).toBeTruthy();
    expect(screen.getByText('jobs')).toBeTruthy();
    expect(screen.getByText('audit')).toBeTruthy();
  });
});

describe('AdminDomainCards', () => {
  it('renders all four domain cards', () => {
    renderWithProviders(<AdminDomainCards health={MOCK_HEALTH} />);
    expect(screen.getByText('Coverage')).toBeTruthy();
    expect(screen.getByText('Stage Quality')).toBeTruthy();
    expect(screen.getAllByText(/Jobs/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Market Audit')).toBeTruthy();
  });

  it('shows job success rate', () => {
    renderWithProviders(<AdminDomainCards health={MOCK_HEALTH} />);
    expect(screen.getAllByText(/80\.0%/).length).toBeGreaterThanOrEqual(1);
  });

  it('shows latest failure task name', () => {
    renderWithProviders(<AdminDomainCards health={MOCK_HEALTH} />);
    expect(screen.getAllByText(/backfill_daily/).length).toBeGreaterThanOrEqual(1);
  });

  it('renders nothing when health is null', () => {
    renderWithProviders(<AdminDomainCards health={null} />);
    expect(screen.queryByText('Stage Quality')).toBeNull();
  });
});

describe('CoverageHealthStrip', () => {
  const FILL_ROWS = [
    { date: '2026-01-06', symbol_count: 480, pct_of_universe: 96.0 },
    { date: '2026-01-07', symbol_count: 490, pct_of_universe: 98.0 },
    { date: '2026-01-08', symbol_count: 500, pct_of_universe: 100.0 },
  ];
  const SNAPSHOT_ROWS = [
    { date: '2026-01-06', symbol_count: 460, pct_of_universe: 92.0 },
    { date: '2026-01-07', symbol_count: 490, pct_of_universe: 98.0 },
    { date: '2026-01-08', symbol_count: 500, pct_of_universe: 100.0 },
  ];

  it('renders heatmap cells with title attributes', () => {
    const { container } = renderWithProviders(
      <CoverageHealthStrip
        dailyFillSeries={FILL_ROWS}
        snapshotFillSeries={SNAPSHOT_ROWS}
        windowDays={50}
        totalSymbols={500}
      />,
    );
    expect(container.querySelectorAll('[title]').length).toBeGreaterThanOrEqual(3);
  });

  it('renders inline sparkline SVG', () => {
    const { container } = renderWithProviders(
      <CoverageHealthStrip
        dailyFillSeries={FILL_ROWS}
        snapshotFillSeries={SNAPSHOT_ROWS}
        windowDays={50}
        totalSymbols={500}
      />,
    );
    expect(container.querySelector('svg')).toBeTruthy();
    expect(container.querySelector('path')).toBeTruthy();
  });

  it('shows latest fill percentage', () => {
    renderWithProviders(
      <CoverageHealthStrip
        dailyFillSeries={FILL_ROWS}
        snapshotFillSeries={SNAPSHOT_ROWS}
        windowDays={50}
        totalSymbols={500}
      />,
    );
    expect(screen.getAllByText(/100/).length).toBeGreaterThanOrEqual(1);
  });

  it('returns null with empty data', () => {
    const { container } = renderWithProviders(
      <CoverageHealthStrip dailyFillSeries={[]} windowDays={50} totalSymbols={0} />,
    );
    expect(container.querySelector('svg')).toBeNull();
  });
});

describe('AdminRunbook', () => {
  it('shows "all healthy" message when all dimensions are green', async () => {
    const user = userEvent.setup();
    const greenHealth: AdminHealthResponse = {
      ...MOCK_HEALTH,
      composite_status: 'green',
      dimensions: {
        ...MOCK_HEALTH.dimensions,
        jobs: { ...MOCK_HEALTH.dimensions.jobs, status: 'green' },
      },
    };
    renderWithProviders(<AdminRunbook health={greenHealth} />);
    const header = screen.getByText(/Runbook/);
    await user.click(header);
    expect(screen.getByText(/All systems healthy/)).toBeTruthy();
  });

  it('shows remediation for RED dimensions', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminRunbook health={MOCK_HEALTH} />);
    const header = screen.getByText(/Runbook.*1 issue/);
    expect(header).toBeTruthy();
    await user.click(header);
    expect(screen.getByText(/One or more background jobs have failed/)).toBeTruthy();
    expect(screen.getByText(/Settings > Admin > Jobs/)).toBeTruthy();
  });

  it('renders nothing when health is null', () => {
    renderWithProviders(<AdminRunbook health={null} />);
    expect(screen.queryByText(/Runbook/)).toBeNull();
  });
});
