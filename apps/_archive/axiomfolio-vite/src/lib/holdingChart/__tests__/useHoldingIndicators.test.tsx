import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';

vi.mock('@/services/api', () => {
  return {
    marketDataApi: {
      getIndicatorSeries: vi.fn(),
    },
  };
});

import { marketDataApi } from '@/services/api';
import {
  __test,
  useHoldingIndicators,
} from '../useHoldingIndicators';

const mockGet = vi.mocked(marketDataApi.getIndicatorSeries);

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

beforeEach(() => {
  mockGet.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useHoldingIndicators (pure transforms)', () => {
  it('extractResponse tolerates wrapped + flat envelopes', () => {
    const flat = {
      symbol: 'AAPL',
      rows: 1,
      backfill_requested: false,
      price_data_pending: false,
      series: { dates: ['2026-01-01'] },
    };
    expect(__test.extractResponse(flat)?.symbol).toBe('AAPL');
    expect(__test.extractResponse({ data: flat })?.symbol).toBe('AAPL');
    expect(__test.extractResponse(null)).toBeNull();
    expect(__test.extractResponse({})).toBeNull();
  });

  it('buildSeries drops nulls and non-finite cells', () => {
    const dates = ['2026-01-01', '2026-01-02', '2026-01-03', '2026-01-04'];
    const cells = [10, null, '12.5', 'not-a-number'];
    expect(__test.buildSeries(dates, cells)).toEqual([
      { time: '2026-01-01', value: 10 },
      { time: '2026-01-03', value: 12.5 },
    ]);
  });

  it('buildSeries truncates to the shorter array', () => {
    const dates = ['2026-01-01', '2026-01-02', '2026-01-03'];
    expect(__test.buildSeries(dates, [1, 2])).toHaveLength(2);
  });

  it('buildStageSegments collapses contiguous identical labels', () => {
    const dates = ['d1', 'd2', 'd3', 'd4', 'd5'];
    const labels = ['2A', '2A', '2B', '2B', '2B'];
    expect(__test.buildStageSegments(dates, labels)).toEqual([
      { startTime: 'd1', endTime: 'd2', label: '2A' },
      { startTime: 'd3', endTime: 'd5', label: '2B' },
    ]);
  });

  it('buildStageSegments breaks runs on null/empty cells', () => {
    const dates = ['d1', 'd2', 'd3', 'd4'];
    const labels = ['2A', null, '2A', '2A'];
    expect(__test.buildStageSegments(dates, labels)).toEqual([
      { startTime: 'd1', endTime: 'd1', label: '2A' },
      { startTime: 'd3', endTime: 'd4', label: '2A' },
    ]);
  });

  it('buildStageSegments returns [] for missing column', () => {
    expect(__test.buildStageSegments(['d1'], undefined)).toEqual([]);
  });
});

describe('useHoldingIndicators (hook)', () => {
  it('does not fetch when indicators is empty', async () => {
    const { result } = renderHook(
      () =>
        useHoldingIndicators({
          symbol: 'AAPL',
          period: '1y',
          indicators: [],
        }),
      { wrapper: makeWrapper() },
    );
    expect(result.current.isLoading).toBe(false);
    expect(mockGet).not.toHaveBeenCalled();
  });

  it('does not fetch when symbol is empty', async () => {
    const { result } = renderHook(
      () =>
        useHoldingIndicators({
          symbol: '',
          period: '1y',
          indicators: ['rsi'],
        }),
      { wrapper: makeWrapper() },
    );
    expect(result.current.isLoading).toBe(false);
    expect(mockGet).not.toHaveBeenCalled();
  });

  it('processes the response into series and stageSegments', async () => {
    mockGet.mockResolvedValueOnce({
      data: {
        symbol: 'AAPL',
        rows: 4,
        backfill_requested: false,
        price_data_pending: false,
        series: {
          dates: ['2026-01-01', '2026-01-02', '2026-01-03', '2026-01-04'],
          rsi: [30, 40, null, '55'],
          stage_label: ['2A', '2A', '2B', '2B'],
        },
      },
    });

    const { result } = renderHook(
      () =>
        useHoldingIndicators({
          symbol: 'AAPL',
          period: '1y',
          indicators: ['rsi', 'stage_label'],
        }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.series.rsi).toEqual([
      { time: '2026-01-01', value: 30 },
      { time: '2026-01-02', value: 40 },
      { time: '2026-01-04', value: 55 },
    ]);
    expect(result.current.series.stage_label).toBeUndefined();
    expect(result.current.stageSegments).toEqual([
      { startTime: '2026-01-01', endTime: '2026-01-02', label: '2A' },
      { startTime: '2026-01-03', endTime: '2026-01-04', label: '2B' },
    ]);
    expect(result.current.rows).toBe(4);
  });

  it('shares the cache regardless of indicator order (sort + dedupe)', async () => {
    mockGet.mockResolvedValue({
      data: {
        symbol: 'AAPL',
        rows: 1,
        backfill_requested: false,
        price_data_pending: false,
        series: {
          dates: ['2026-01-01'],
          rsi: [50],
          sma_50: [100],
        },
      },
    });

    // We render TWO hooks against the SAME QueryClient. If the queryKey
    // is order-stable, the second render hits the cache and we still
    // see only one network call.
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 60_000 } },
    });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { result: r1 } = renderHook(
      () =>
        useHoldingIndicators({
          symbol: 'AAPL',
          period: '1y',
          indicators: ['rsi', 'sma_50'],
        }),
      { wrapper },
    );
    await waitFor(() => expect(r1.current.isLoading).toBe(false));

    renderHook(
      () =>
        useHoldingIndicators({
          symbol: 'AAPL',
          period: '1y',
          indicators: ['sma_50', 'rsi', 'rsi'],
        }),
      { wrapper },
    );

    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(mockGet).toHaveBeenCalledWith('AAPL', {
      period: '1y',
      indicators: ['rsi', 'sma_50'],
    });
  });

  it('surfaces backfill / price-pending signals from the payload', async () => {
    mockGet.mockResolvedValueOnce({
      data: {
        symbol: 'AAPL',
        rows: 0,
        backfill_requested: true,
        price_data_pending: true,
        series: { dates: [] },
      },
    });

    const { result } = renderHook(
      () =>
        useHoldingIndicators({
          symbol: 'AAPL',
          period: '1y',
          indicators: ['rsi'],
        }),
      { wrapper: makeWrapper() },
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.backfillRequested).toBe(true);
    expect(result.current.pricePending).toBe(true);
    expect(result.current.rows).toBe(0);
    expect(result.current.series.rsi).toEqual([]);
  });
});
