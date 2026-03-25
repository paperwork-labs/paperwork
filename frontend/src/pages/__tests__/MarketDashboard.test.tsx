import React from 'react';
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';
import { screen, fireEvent, waitFor, cleanup } from '@/test/testing-library';
import { renderWithProviders } from '../../test/render';
import { marketDataApi } from '../../services/api';
import MarketDashboard from '../MarketDashboard';

vi.mock('../../components/charts/TradingViewChart', () => ({
  default: ({ symbol }: { symbol: string }) => <div data-testid="tv-chart">{symbol}</div>,
}));

vi.mock('../../hooks/usePortfolioSymbols', () => ({
  usePortfolioSymbols: () => ({ data: {}, isLoading: false }),
}));

vi.mock('../../services/api', () => {
  return {
    default: { get: vi.fn().mockResolvedValue({ data: {} }) },
    marketDataApi: {
      // RegimeBanner: getCurrentRegime() returns axios body; queryFn reads resp.data.regime
      getCurrentRegime: vi.fn().mockResolvedValue({
        data: {
          regime: {
            regime_state: 'R2',
            composite_score: 2.2,
            as_of_date: '2026-01-08',
            regime_multiplier: 0.75,
            max_equity_exposure_pct: 90,
            cash_floor_pct: 10,
            vix_spot: null,
            vix3m_vix_ratio: null,
            vvix_vix_ratio: null,
            nh_nl: null,
            pct_above_200d: null,
            pct_above_50d: null,
          },
        },
      }),
      getHistory: vi.fn().mockResolvedValue({
        bars: [
          { close: 100 }, { close: 101 }, { close: 102 }, { close: 103 }, { close: 104 },
        ],
      }),
      getSnapshot: vi.fn().mockResolvedValue({ data: { stage_label: '2A', current_stage_days: 5 } }),
      getVolatilityDashboard: vi.fn().mockResolvedValue({}),
      getDashboard: vi.fn().mockResolvedValue({
        tracked_count: 120,
        snapshot_count: 118,
        entry_proximity_top: [{ symbol: 'NVDA', entry_price: 100, distance_pct: 1.2, distance_atr: 0.6 }],
        exit_proximity_top: [{ symbol: 'MSFT', exit_price: 420, distance_pct: 2.1, distance_atr: 0.9 }],
        sector_etf_table: [{ symbol: 'XLK', sector_name: 'Technology', change_1d: 0.9, stage_label: '2A', days_in_stage: 3 }],
        entering_stage_2a: [{ symbol: 'AAPL', previous_stage_label: '1' }],
        regime: { stage_counts_normalized: { '1': 10, '2A': 5, '2B': 3, '2C': 2, '3': 1, '4': 1 } },
        action_queue: [
          { symbol: 'TSLA', stage_label: '2A', previous_stage_label: '1', perf_1d: 5.2, rs_mansfield_pct: 2.0, sector: 'Consumer Discretionary' },
        ],
        range_histogram: [
          { bin: '0-10%', count: 5 }, { bin: '10-20%', count: 8 }, { bin: '20-30%', count: 12 },
          { bin: '30-40%', count: 15 }, { bin: '40-50%', count: 20 }, { bin: '50-60%', count: 18 },
          { bin: '60-70%', count: 14 }, { bin: '70-80%', count: 10 }, { bin: '80-90%', count: 7 },
          { bin: '90-100%', count: 3 },
        ],
        rrg_sectors: [
          { symbol: 'XLK', name: 'Technology', rs_ratio: 3.5, rs_momentum: 1.2 },
          { symbol: 'XLE', name: 'Energy', rs_ratio: -2.1, rs_momentum: -0.8 },
        ],
        rsi_divergences: {
          bearish: [{ symbol: 'AMD', perf_20d: 8.5, rsi: 42, stage_label: '2B' }],
          bullish: [{ symbol: 'BA', perf_20d: -6.2, rsi: 55, stage_label: '3' }],
        },
        td_signals: [
          { symbol: 'GOOG', signals: ['Buy Setup 9'], stage_label: '2A', perf_1d: 1.5 },
        ],
        gap_leaders: [
          { symbol: 'META', gaps_up: 3, gaps_down: 2, total_gaps: 5, stage_label: '2A' },
        ],
        fundamental_leaders: [
          { symbol: 'NVDA', eps_growth_yoy: 45, rs_mansfield_pct: 6.2, pe_ttm: 55, stage_label: '2A', composite_score: 25.6 },
        ],
        top10_matrix: {
          perf_1d: [{ symbol: 'NVDA', value: 2.3 }],
          perf_5d: [{ symbol: 'NVDA', value: 4.4 }],
          perf_20d: [{ symbol: 'NVDA', value: 12.1 }],
          atrx_sma_21: [{ symbol: 'NVDA', value: 1.2 }],
          atrx_sma_50: [{ symbol: 'NVDA', value: 2.2 }],
          atrx_sma_200: [{ symbol: 'NVDA', value: 3.1 }],
        },
        bottom10_matrix: {
          perf_1d: [{ symbol: 'XOM', value: -1.3 }],
          perf_5d: [{ symbol: 'XOM', value: -2.4 }],
          perf_20d: [{ symbol: 'XOM', value: -7.1 }],
          atrx_sma_21: [{ symbol: 'XOM', value: -1.2 }],
          atrx_sma_50: [{ symbol: 'XOM', value: -2.2 }],
          atrx_sma_200: [{ symbol: 'XOM', value: -3.1 }],
        },
      }),
    },
  };
});

describe('MarketDashboard', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    // Avoid flakes: ETF/holdings filter or collapsed "ranked" hides matrices; persisted view breaks overview.
    localStorage.removeItem('axiomfolio:dashboard:collapsed');
    localStorage.removeItem('axiomfolio:dashboard:view');
    localStorage.removeItem('axiomfolio:market-dashboard:universe-filter');
  });

  it('renders loading state before data is shown', () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    expect(screen.getByText(/Loading market dashboard/i)).toBeInTheDocument();
  });

  it('shows default market state with empty data', async () => {
    vi.mocked(marketDataApi.getDashboard).mockImplementationOnce(async () => ({
      tracked_count: 0,
      snapshot_count: 0,
      regime: { stage_counts_normalized: {} },
    }));
    renderWithProviders(<MarketDashboard />, { route: '/' });
    await waitFor(
      () => {
        expect(screen.queryByText(/Loading market dashboard/i)).not.toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    const titles = await screen.findAllByText('Market Dashboard');
    expect(titles.length).toBeGreaterThanOrEqual(1);
    // Overview uses API snapshot_count when universe has no constituent list (empty dashboard).
    expect(screen.getAllByText('0 / 0').length).toBeGreaterThanOrEqual(2);
  });

  it('marks repeated symbols across matrix columns', async () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });

    const repeatedTop = await screen.findAllByTestId('repeat-text-top-10-matrix');
    const repeatedBottom = await screen.findAllByTestId('repeat-text-bottom-10-matrix');

    expect(repeatedTop.length).toBeGreaterThan(1);
    expect(repeatedBottom.length).toBeGreaterThan(1);
  });

  it('renders action queue section', async () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    const items = await screen.findAllByText('Action Queue');
    expect(items.length).toBeGreaterThanOrEqual(1);
    expect(await screen.findAllByText('TSLA')).toBeDefined();
  });

  it('renders 52-week range histogram section', async () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    const items = await screen.findAllByText('52-Week Range Distribution');
    expect(items.length).toBeGreaterThanOrEqual(1);
  });

  it('renders RRG sector chart', async () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    const items = await screen.findAllByText('Relative Rotation Graph (Sectors)');
    expect(items.length).toBeGreaterThanOrEqual(1);
  });

  it('renders divergence watch section', async () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    const items = await screen.findAllByText('Divergence Watch');
    expect(items.length).toBeGreaterThanOrEqual(1);
  });

  it('renders TD Sequential signals section', async () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    const items = await screen.findAllByText('TD Sequential Signals');
    expect(items.length).toBeGreaterThanOrEqual(1);
  });

  it('renders open gaps section', async () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    const items = await screen.findAllByText('Open Gaps');
    expect(items.length).toBeGreaterThanOrEqual(1);
  });

  it('renders fundamental leaders section', async () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    const items = await screen.findAllByText('Fundamental Leaders');
    expect(items.length).toBeGreaterThanOrEqual(1);
  });

  it('clicking a symbol opens the TradingView slide-out panel', async () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    const tslaLinks = await screen.findAllByText('TSLA');
    expect(tslaLinks.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(tslaLinks[0]);
    await waitFor(() => {
      expect(screen.getByTestId('tv-chart')).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('does not navigate to market-tracked when clicking a symbol', async () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    const tslaLinks = await screen.findAllByText('TSLA');
    expect(tslaLinks.length).toBeGreaterThanOrEqual(1);
    const link = tslaLinks[0].closest('a');
    expect(link).toBeNull();
  });
});
