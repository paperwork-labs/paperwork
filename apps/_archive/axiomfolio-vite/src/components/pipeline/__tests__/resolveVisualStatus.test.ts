import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';
import {
  STALE_AGE_MS,
  isStaleByAge,
  resolveVisualStatus,
} from '../PipelineDAG';
import type { PipelineStepState } from '@/types/pipeline';

const NOW = new Date('2026-04-15T12:00:00Z').getTime();

beforeAll(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterAll(() => {
  vi.useRealTimers();
});

function step(
  status: PipelineStepState['status'],
  ageMs: number,
): PipelineStepState {
  const ts = new Date(NOW - ageMs).toISOString();
  return {
    status,
    started_at: ts,
    finished_at: ts,
    duration_s: 1.2,
    error: status === 'error' ? 'boom' : null,
    counters: null,
  };
}

describe('isStaleByAge', () => {
  it('returns false when no timestamps are set', () => {
    expect(isStaleByAge(undefined)).toBe(false);
    expect(
      isStaleByAge({
        status: 'ok',
        started_at: null,
        finished_at: null,
        duration_s: null,
        error: null,
        counters: null,
      }),
    ).toBe(false);
  });

  it('returns false for fresh events', () => {
    expect(isStaleByAge(step('ok', 60_000))).toBe(false);
    expect(isStaleByAge(step('error', STALE_AGE_MS - 1_000))).toBe(false);
  });

  it('returns true once last event is older than STALE_AGE_MS', () => {
    expect(isStaleByAge(step('error', STALE_AGE_MS + 60_000))).toBe(true);
    expect(isStaleByAge(step('ok', STALE_AGE_MS * 3))).toBe(true);
  });

  it('handles invalid timestamps gracefully', () => {
    expect(
      isStaleByAge({
        status: 'error',
        started_at: 'not-a-date',
        finished_at: null,
        duration_s: null,
        error: 'x',
        counters: null,
      }),
    ).toBe(false);
  });
});

describe('resolveVisualStatus', () => {
  it('keeps fresh error as error (red)', () => {
    const s = step('error', 60_000);
    expect(resolveVisualStatus('error', 'indicators', null, [], { indicators: s }, s)).toBe(
      'error',
    );
  });

  it('downgrades stale error to stale (gray) when both real + ambient are old', () => {
    const stale = step('error', STALE_AGE_MS + 3600_000);
    expect(resolveVisualStatus('error', 'indicators', null, [], { indicators: stale }, stale)).toBe(
      'stale',
    );
  });

  it('does NOT downgrade error if ambient state is fresh (recently re-ran)', () => {
    const stale = step('error', STALE_AGE_MS + 3600_000);
    const fresh = step('error', 60_000);
    expect(resolveVisualStatus('error', 'indicators', null, [], { indicators: fresh }, stale)).toBe(
      'error',
    );
  });

  it('downgrades stale ok to stale so >12h-old success cells go gray', () => {
    const stale = step('ok', STALE_AGE_MS + 3600_000);
    expect(resolveVisualStatus('ok', 'indicators', null, [], { indicators: stale }, stale)).toBe(
      'stale',
    );
  });

  it('keeps running over everything (active task overrides stale ambient)', () => {
    const stale = step('error', STALE_AGE_MS + 3600_000);
    const result = resolveVisualStatus(
      'pending',
      'indicators',
      null,
      [{ id: 'x', name: 'admin_indicators_recompute_universe', worker: 'w', started: NOW, dag_step: 'indicators' }],
      { indicators: stale },
      stale,
    );
    expect(result).toBe('running');
  });

  it('returns pending unchanged when nothing is known and no health override applies', () => {
    expect(resolveVisualStatus('pending', 'indicators', null, [], {}, undefined)).toBe(
      'pending',
    );
  });
});
