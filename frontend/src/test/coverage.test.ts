import { describe, it, expect } from 'vitest';
import {
  deriveSparklineSeries,
  buildCoverageKpis,
  buildCoverageActions,
  getCoverageStatusColor,
  formatCoverageHero,
} from '../utils/coverage';

describe('deriveSparklineSeries', () => {
  it('returns meta sparkline when present', () => {
    const meta = {
      daily_pct: [90, 95],
      m5_pct: [80, 85],
      labels: ['a', 'b'],
      stale_daily: [1, 2],
      stale_m5: [0, 1],
    };
    const result = deriveSparklineSeries(meta, null);
    expect(result.daily_pct).toEqual([90, 95]);
    expect(result.labels).toEqual(['a', 'b']);
  });

  it('builds sparkline from history fallback', () => {
    const history = [
      { ts: 't1', daily_pct: 80, m5_pct: 60, stale_daily: 5, stale_m5: 2 },
      { ts: 't2', daily_pct: 90, m5_pct: 70, stale_daily: 3, stale_m5: 1 },
    ];
    const result = deriveSparklineSeries(null, history);
    expect(result.daily_pct).toEqual([80, 90]);
    expect(result.m5_pct).toEqual([60, 70]);
    expect(result.labels).toEqual(['t1', 't2']);
    expect(result.stale_daily).toEqual([5, 3]);
  });
});

describe('buildCoverageKpis', () => {
  it('returns meta KPIs when provided', () => {
    const meta = [{ id: 'tracked', label: 'Tracked', value: 10 }];
    expect(buildCoverageKpis(meta, {}, {})).toBe(meta);
  });

  it('builds fallback KPIs when missing', () => {
    const snapshot = { tracked_count: 3, symbols: 4, daily: { count: 3 }, m5: { count: 2 } };
    const status = { daily_pct: 75, m5_pct: 50, stale_daily: 1, stale_m5: 1 };
    const kpis = buildCoverageKpis(undefined, snapshot, status);
    expect(kpis).toHaveLength(4);
    expect(kpis[0].value).toBe(3);
    expect(kpis[1].value).toBe(75);
  });
});

describe('coverage helpers', () => {
  it('buildCoverageActions merges defaults without duplicates', () => {
    const actions = buildCoverageActions([
      { label: 'Custom', task_name: 'custom_task' },
      { label: 'Backfill Daily Coverage Override', task_name: 'admin_coverage_backfill' },
    ]);
    expect(actions.find((a) => a.task_name === 'custom_task')).toBeTruthy();
    expect(actions.filter((a) => a.task_name === 'admin_coverage_backfill')).toHaveLength(1);
    expect(actions.some((a) => a.task_name === 'admin_snapshots_history_record')).toBe(true);
  });

  it('getCoverageStatusColor maps known statuses', () => {
    expect(getCoverageStatusColor('ok')).toBe('green');
    expect(getCoverageStatusColor('warning')).toBe('yellow');
    expect(getCoverageStatusColor('unknown')).toBe('orange');
  });

  it('formatCoverageHero produces bucket + banner metadata', () => {
    const snapshot = {
      status: { label: 'warning', summary: 'Needs attention', stale_daily: 2, stale_m5: 1 },
      meta: {
        updated_at: new Date('2024-01-01T00:00:00Z').toISOString(),
        source: 'cache',
        snapshot_age_seconds: 600,
        sla: { daily_pct: 95 },
      },
      daily: { freshness: { '<=24h': 10, '24-48h': 1, '>48h': 0, none: 0 } },
      m5: { freshness: { '<=24h': 8, '24-48h': 2, '>48h': 1, none: 0 } },
    };
    const hero = formatCoverageHero(snapshot);
    expect(hero.statusLabel).toBe('WARNING');
    expect(hero.statusColor).toBe('yellow');
    expect(hero.buckets[0].buckets[0].count).toBe(10);
    expect(hero.warningBanner?.title).toContain('warning');
  });

  it('marks snapshot stale when age exceeds threshold', () => {
    const snapshot = {
      status: { label: 'ok', summary: 'All good', stale_daily: 0, stale_m5: 0 },
      meta: {
        updated_at: new Date('2024-01-01T00:00:00Z').toISOString(),
        source: 'cache',
        snapshot_age_seconds: 7200,
      },
      daily: { freshness: { '<=24h': 1 } },
      m5: { freshness: { '<=24h': 1 } },
    };
    const hero = formatCoverageHero(snapshot, 1800);
    expect(hero.isSnapshotStale).toBe(true);
    expect(hero.warningBanner?.title).toContain('Snapshot is stale');
  });
});

