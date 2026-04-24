import { describe, expect, it } from 'vitest';
import { deriveSparklineSeries, formatCoverageHero } from '../coverage';

describe('formatCoverageHero', () => {
  it('computes tracked, universe, and bucket metadata', () => {
    const snapshot = {
      status: {
        label: 'ok',
        summary: 'All systems nominal',
        stale_daily: 2,
        stale_m5: 1,
      },
      tracked_count: 50,
      symbols: 60,
      generated_at: '2025-01-01T00:00:00Z',
      daily: {
        freshness: { '<=24h': 40, '24-48h': 10, '>48h': 5, none: 5 },
      },
      m5: {
        freshness: { '<=24h': 20, '24-48h': 15, '>48h': 10, none: 15 },
      },
      history: [
        { ts: '2025-01-01T00:00:00Z', daily_pct: 90, m5_pct: 80, stale_daily: 2, stale_m5: 1 },
      ],
      meta: {
        updated_at: '2025-01-01T00:00:00Z',
        history: [
          { ts: '2025-01-01T00:00:00Z', daily_pct: 90, m5_pct: 80, stale_daily: 2, stale_m5: 1 },
        ],
      },
    };

    const hero = formatCoverageHero(snapshot);

    expect(hero.trackedCount).toBe(50);
    expect(hero.totalSymbols).toBe(60);
    expect(hero.historySamples).toBe(1);
    expect(hero.buckets[0].buckets[0].count).toBe(40);
    expect(hero.staleCounts.daily).toBe(2);
    expect(hero.staleCounts.m5).toBe(1);
  });

  it('marks snapshot stale when age exceeds threshold', () => {
    const updatedAt = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    const snapshot = {
      status: { label: 'warning', summary: 'Stale snapshot' },
      tracked_count: 0,
      symbols: 0,
      meta: {
        updated_at: updatedAt,
        snapshot_age_seconds: 4000,
      },
    };

    const hero = formatCoverageHero(snapshot, 1800);

    expect(hero.isSnapshotStale).toBe(true);
    expect(hero.warningBanner?.status).toBe('warning');
  });
});

describe('deriveSparklineSeries', () => {
  it('prefers meta sparkline payload when available', () => {
    const metaSeries = {
      daily_pct: [95, 96],
      m5_pct: [70, 75],
      labels: ['t-1', 't'],
      stale_daily: [5, 4],
      stale_m5: [10, 9],
    };
    const history = [
      { ts: 'older', daily_pct: 80, m5_pct: 60, stale_daily: 10, stale_m5: 15 },
    ];

    const sparkline = deriveSparklineSeries(metaSeries as any, history);

    expect(sparkline.daily_pct).toEqual([95, 96]);
    expect(sparkline.labels).toEqual(['t-1', 't']);
    expect(sparkline.stale_daily).toEqual([5, 4]);
  });

  it('falls back to history when meta sparkline missing', () => {
    const history = [
      { ts: '2025-01-01', daily_pct: 92, m5_pct: 80, stale_daily: 3, stale_m5: 6 },
      { ts: '2025-01-02', daily_pct: 94, m5_pct: 82, stale_daily: 2, stale_m5: 5 },
    ];

    const sparkline = deriveSparklineSeries(undefined, history);

    expect(sparkline.daily_pct).toEqual([92, 94]);
    expect(sparkline.labels).toEqual(['2025-01-01', '2025-01-02']);
    expect(sparkline.stale_m5).toEqual([6, 5]);
  });
});






