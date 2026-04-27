import React from 'react';
import { useColorMode } from '@axiomfolio/theme/colorMode';
import FinvizHeatMap from '@axiomfolio/components/charts/FinvizHeatMap';
import TradingViewChart from '@axiomfolio/components/charts/TradingViewChart';
import SymbolChartWithMarkers from '@axiomfolio/components/charts/SymbolChartWithMarkers';
import BarHistogram, { TimeSeriesBar } from '@axiomfolio/components/charts/BarHistogram';
import { ChartContext, SymbolLink, ChartSlidePanel } from '@axiomfolio/components/market/SymbolChartUI';
import type { Meta, StoryObj } from "@storybook/react";

const meta: Meta = {
  title: 'DesignSystem/Charts',
};
export default meta;

type Story = StoryObj;

const heatmap = [
  { name: 'AAPL', size: 10, change: 1.8, sector: 'Tech', value: 182_000 },
  { name: 'MSFT', size: 9, change: -0.7, sector: 'Tech', value: 165_000 },
  { name: 'NVDA', size: 8, change: 3.6, sector: 'Tech', value: 144_000 },
  { name: 'AMZN', size: 7, change: -2.3, sector: 'Consumer', value: 128_000 },
  { name: 'TSLA', size: 6, change: 0.4, sector: 'Auto', value: 110_000 },
  { name: 'JPM', size: 5, change: -4.1, sector: 'Financials', value: 92_000 },
];

const successRgb = 'rgb(var(--status-success) / 1)';
const brandBlue = '#3b82f6';

export const FinvizHeatMap_Basic: Story = {
  render: () => (
  <div className="p-6">
    <FinvizHeatMap data={heatmap as any} height={360} />
  </div>
),
};

export const TradingViewChart_Example: Story = {
  render: () => {
  const { colorMode, toggleColorMode } = useColorMode();
  return (
    <div className="p-6">
      <button
        type="button"
        onClick={toggleColorMode}
        className="rounded-[10px] border border-border px-3 py-2 text-sm"
      >
        Toggle mode ({colorMode})
      </button>
      <div className="mt-4">
        <TradingViewChart symbol="AAPL" height={520} />
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        Note: this loads TradingView’s external embed script at runtime.
      </p>
    </div>
  );
},
};

export const SymbolLink_AndChartPanel: Story = {
  render: () => {
  const [chartSymbol, setChartSymbol] = React.useState<string | null>(null);
  const openChart = React.useCallback((sym: string) => setChartSymbol(sym), []);
  return (
    <ChartContext.Provider value={openChart}>
      <div className="p-6">
        <p className="mb-3 text-sm text-muted-foreground">
          Hover a symbol for sparkline; click to open the TradingView chart panel.
        </p>
        <div className="flex flex-row flex-wrap gap-4">
          <SymbolLink symbol="AAPL" />
          <SymbolLink symbol="MSFT" />
          <SymbolLink symbol="NVDA" />
          <SymbolLink symbol="SPY" />
        </div>
      </div>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
},
};

export const SymbolChartWithMarkers_Example: Story = {
  render: () => {
  const now = Date.now();
  const day = 86400_000;
  const bars = Array.from({ length: 60 }).map((_, i) => {
    const t = new Date(now - (60 - i) * day).toISOString();
    const base = 100 + i * 0.4;
    return { time: t, open: base - 0.6, high: base + 1.2, low: base - 1.1, close: base + (i % 2 ? 0.7 : -0.3) };
  });
  const events = [
    { time: bars[10].time, price: 102.3, type: 'BUY' as const, label: 'Buy 10' },
    { time: bars[40].time, price: 114.1, type: 'SELL' as const, label: 'Sell 5' },
    { time: bars[25].time, price: 106, type: 'DIVIDEND' as const, label: 'Div $0.22', amount: 0.22 },
  ];

  return (
    <div className="p-6">
      <div className="rounded-xl border border-border bg-card p-3">
        <SymbolChartWithMarkers bars={bars} events={events} height={420} />
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        Note: this loads LightweightCharts from a CDN at runtime.
      </p>
    </div>
  );
},
};

export const BarHistogram_52WeekRange: Story = {
  render: () => {
  const bins = [
    { label: '0-10', value: 33, zone: 'danger' as const },
    { label: '10-20', value: 21, zone: 'danger' as const },
    { label: '20-30', value: 42, zone: 'neutral' as const },
    { label: '30-40', value: 39, zone: 'neutral' as const },
    { label: '40-50', value: 44, zone: 'neutral' as const },
    { label: '50-60', value: 38, zone: 'neutral' as const },
    { label: '60-70', value: 39, zone: 'neutral' as const },
    { label: '70-80', value: 43, zone: 'neutral' as const },
    { label: '80-90', value: 101, zone: 'success' as const },
    { label: '90-95', value: 171, zone: 'success' as const },
  ];
  return (
    <div className="p-6 max-w-[500px]">
      <div className="rounded-lg border border-border bg-card p-4">
        <BarHistogram bins={bins} height={180} title="52-Week Range Distribution" subtitle="Left-skew = capitulation · Right-skew = euphoria" />
      </div>
    </div>
  );
},
};

export const TimeSeriesBar_Breadth: Story = {
  render: () => {
  const data = Array.from({ length: 30 }, (_, i) => ({
    date: `2026-01-${String(i + 1).padStart(2, '0')}`,
    values: [
      { value: 40 + Math.sin(i / 3) * 20 + ((i * 7) % 10), color: successRgb, label: '>50DMA' },
      { value: 30 + Math.cos(i / 4) * 15 + ((i * 5 + 3) % 8), color: brandBlue, label: '>200DMA' },
    ],
  }));
  return (
    <div className="p-6 max-w-[500px]">
      <div className="rounded-lg border border-border bg-card p-4">
        <TimeSeriesBar
          data={data}
          height={160}
          title="Breadth Over Time (60d)"
          legend={[
            { color: successRgb, label: '% > 50DMA' },
            { color: brandBlue, label: '% > 200DMA' },
          ]}
        />
      </div>
    </div>
  );
},
};
