import * as React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const setDataMock = vi.fn();
const createChartMock = vi.fn();
const removeMock = vi.fn();

vi.mock('lightweight-charts', () => {
  const stubSeries = () => ({ setData: setDataMock, createPriceLine: vi.fn() });
  return {
    CandlestickSeries: { __kind: 'Candlestick' },
    AreaSeries: { __kind: 'Area' },
    LineSeries: { __kind: 'Line' },
    HistogramSeries: { __kind: 'Histogram' },
    LineStyle: { Dotted: 1, Dashed: 2, Solid: 0 },
    createChart: () => {
      createChartMock();
      return {
        addSeries: () => stubSeries(),
        addPane: () => ({
          setStretchFactor: vi.fn(),
          addSeries: () => stubSeries(),
        }),
        timeScale: () => ({
          setVisibleRange: vi.fn(),
          fitContent: vi.fn(),
          subscribeVisibleTimeRangeChange: vi.fn(),
        }),
        subscribeCrosshairMove: vi.fn(),
        subscribeClick: vi.fn(),
        remove: removeMock,
      };
    },
    createSeriesMarkers: vi.fn(),
  };
});

import { ColorModeProvider } from '../../../theme/colorMode';
import SymbolChartWithMarkers from '../SymbolChartWithMarkers';

function renderWithTheme(ui: React.ReactElement) {
  return render(<ColorModeProvider>{ui}</ColorModeProvider>);
}

describe('SymbolChartWithMarkers', () => {
  beforeEach(() => {
    setDataMock.mockClear();
    createChartMock.mockClear();
    removeMock.mockClear();
  });

  it('shows empty state when bars are empty (no silent blank)', () => {
    renderWithTheme(
      <SymbolChartWithMarkers
        height={200}
        bars={[]}
        events={[]}
        symbol="GOOGL"
      />,
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      /No OHLCV history here yet for GOOGL/,
    );
    expect(createChartMock).not.toHaveBeenCalled();
  });

  it('initializes chart when bars are non-empty', () => {
    const { unmount } = renderWithTheme(
      <SymbolChartWithMarkers
        height={200}
        bars={[
          {
            time: '2024-06-01',
            open: 100,
            high: 105,
            low: 99,
            close: 103,
          },
        ]}
        events={[]}
        symbol="GOOGL"
      />,
    );
    expect(createChartMock).toHaveBeenCalled();
    expect(setDataMock).toHaveBeenCalled();
    unmount();
    expect(removeMock).toHaveBeenCalled();
  });
});
