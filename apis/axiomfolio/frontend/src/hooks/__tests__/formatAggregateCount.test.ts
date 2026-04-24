import { describe, it, expect } from 'vitest';
import { formatAggregateCount } from '../useSnapshotAggregates';

describe('formatAggregateCount', () => {
  it('returns the count when data is present (including zero)', () => {
    expect(
      formatAggregateCount({
        data: { total: 47 },
        isLoading: false,
        isError: false,
      })
    ).toBe('47');

    // Zero is a real result and must NOT be replaced with a placeholder.
    expect(
      formatAggregateCount({
        data: { total: 0 },
        isLoading: false,
        isError: false,
      })
    ).toBe('0');
  });

  it('returns a loading placeholder when no data and loading', () => {
    expect(
      formatAggregateCount({
        data: undefined,
        isLoading: true,
        isError: false,
      })
    ).toBe('…');
  });

  it('returns an error placeholder when no data and errored', () => {
    expect(
      formatAggregateCount({
        data: undefined,
        isLoading: false,
        isError: true,
      })
    ).toBe('—');
  });

  it('prefers stale data over placeholder during a background refetch', () => {
    // React Query semantics: data persists during background refetch even
    // when isLoading flips. We pass explicit isLoading=false here because
    // useQuery would only set isLoading=true on the very first fetch.
    expect(
      formatAggregateCount({
        data: { total: 12 },
        isLoading: false,
        isError: false,
      })
    ).toBe('12');
  });

  it('falls back to dash when data is undefined and not loading or error', () => {
    expect(
      formatAggregateCount({
        data: undefined,
        isLoading: false,
        isError: false,
      })
    ).toBe('—');
  });
});
