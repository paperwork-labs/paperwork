import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChakraProvider } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router-dom';

import { system } from '../../theme/system';
import MarketDashboard from '../MarketDashboard';

const navigate = vi.fn();

vi.mock('../../services/api', () => {
  return {
    marketDataApi: {
      getDashboard: vi.fn().mockResolvedValue({
        tracked_count: 120,
        snapshot_count: 118,
        coverage: { status: 'healthy', daily_pct: 98.2, m5_pct: 73.1 },
        regime: { up_1d_count: 68, down_1d_count: 42 },
        leaders: [
          { symbol: 'NVDA', momentum_score: 12.4, perf_20d: 18.2, rs_mansfield_pct: 6.1 },
          { symbol: 'MSFT', momentum_score: 10.1, perf_20d: 14.5, rs_mansfield_pct: 4.2 },
        ],
        setups: {
          breakout_candidates: [{ symbol: 'AAPL' }, { symbol: 'META' }],
          pullback_candidates: [{ symbol: 'AMZN' }],
          rs_leaders: [{ symbol: 'TSLA' }],
        },
        sector_momentum: [{ sector: 'Technology' }],
        action_queue: [{ symbol: 'NFLX' }],
      }),
    },
  };
});

vi.mock('react-router-dom', async () => {
  const actual: any = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
  };
});

const renderPage = () =>
  render(
    <ChakraProvider value={system}>
      <MemoryRouter initialEntries={['/']}>
        <MarketDashboard />
      </MemoryRouter>
    </ChakraProvider>,
  );

describe('MarketDashboard drill-down links', () => {
  afterEach(() => cleanup());

  it('opens tracked root from Open Tracked link', async () => {
    const user = userEvent.setup();
    navigate.mockClear();
    renderPage();

    await waitFor(() => expect(screen.getByText(/Momentum Leaders/i)).toBeInTheDocument());
    await user.click(screen.getByTestId('open-tracked-momentum-leaders'));
    expect(navigate).toHaveBeenCalledWith('/market/tracked');
  });

  it('navigates to tracked with section symbols from View all N', async () => {
    const user = userEvent.setup();
    navigate.mockClear();
    renderPage();

    await waitFor(() => expect(screen.getByText(/Breakout Candidates/i)).toBeInTheDocument());
    await user.click(screen.getByTestId('view-all-breakout'));
    expect(navigate).toHaveBeenCalledWith('/market/tracked?symbols=AAPL%2CMETA');
  });
});
