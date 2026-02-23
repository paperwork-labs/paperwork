import React from 'react';
import { Box, Text, HStack } from '@chakra-ui/react';
import { useColorMode } from '../theme/colorMode';
import FinvizHeatMap from '../components/charts/FinvizHeatMap';
import TradingViewChart from '../components/charts/TradingViewChart';
import SymbolChartWithMarkers from '../components/charts/SymbolChartWithMarkers';
import BarHistogram, { TimeSeriesBar } from '../components/charts/BarHistogram';
import { ChartContext, SymbolLink, ChartSlidePanel } from '../components/market/SymbolChartUI';

export default {
  title: 'DesignSystem/Charts',
};

const heatmap = [
  { name: 'AAPL', size: 10, change: 1.8, sector: 'Tech', value: 182_000 },
  { name: 'MSFT', size: 9, change: -0.7, sector: 'Tech', value: 165_000 },
  { name: 'NVDA', size: 8, change: 3.6, sector: 'Tech', value: 144_000 },
  { name: 'AMZN', size: 7, change: -2.3, sector: 'Consumer', value: 128_000 },
  { name: 'TSLA', size: 6, change: 0.4, sector: 'Auto', value: 110_000 },
  { name: 'JPM', size: 5, change: -4.1, sector: 'Financials', value: 92_000 },
];

export const FinvizHeatMap_Basic = () => (
  <Box p={6}>
    <FinvizHeatMap data={heatmap as any} height={360} />
  </Box>
);

export const TradingViewChart_Example = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  return (
    <Box p={6}>
      <Text
        as="button"
        onClick={toggleColorMode}
        style={{ padding: '8px 12px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.12)' }}
      >
        Toggle mode ({colorMode})
      </Text>
      <Box mt={4}>
        <TradingViewChart symbol="AAPL" height={520} />
      </Box>
      <Text mt={3} fontSize="xs" color="fg.muted">
        Note: this loads TradingView’s external embed script at runtime.
      </Text>
    </Box>
  );
};

export const SymbolLink_AndChartPanel = () => {
  const [chartSymbol, setChartSymbol] = React.useState<string | null>(null);
  const openChart = React.useCallback((sym: string) => setChartSymbol(sym), []);
  return (
    <ChartContext.Provider value={openChart}>
      <Box p={6}>
        <Text fontSize="sm" color="fg.muted" mb={3}>
          Hover a symbol for sparkline; click to open the TradingView chart panel.
        </Text>
        <HStack gap={4} flexWrap="wrap">
          <SymbolLink symbol="AAPL" />
          <SymbolLink symbol="MSFT" />
          <SymbolLink symbol="NVDA" />
          <SymbolLink symbol="SPY" />
        </HStack>
      </Box>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
};

export const SymbolChartWithMarkers_Example = () => {
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
    <Box p={6}>
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="xl" bg="bg.card" p={3}>
        <SymbolChartWithMarkers bars={bars} events={events} height={420} />
      </Box>
      <Text mt={3} fontSize="xs" color="fg.muted">
        Note: this loads LightweightCharts from a CDN at runtime.
      </Text>
    </Box>
  );
};

export const BarHistogram_52WeekRange = () => {
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
    <Box p={6} maxW="500px">
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
        <BarHistogram bins={bins} height={180} title="52-Week Range Distribution" subtitle="Left-skew = capitulation · Right-skew = euphoria" />
      </Box>
    </Box>
  );
};

export const TimeSeriesBar_Breadth = () => {
  const data = Array.from({ length: 30 }, (_, i) => ({
    date: `2026-01-${String(i + 1).padStart(2, '0')}`,
    values: [
      { value: 40 + Math.sin(i / 3) * 20 + Math.random() * 10, color: 'var(--chakra-colors-status-success)', label: '>50DMA' },
      { value: 30 + Math.cos(i / 4) * 15 + Math.random() * 8, color: 'var(--chakra-colors-brand-500)', label: '>200DMA' },
    ],
  }));
  return (
    <Box p={6} maxW="500px">
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
        <TimeSeriesBar
          data={data}
          height={160}
          title="Breadth Over Time (60d)"
          legend={[
            { color: 'var(--chakra-colors-status-success)', label: '% > 50DMA' },
            { color: 'var(--chakra-colors-brand-500)', label: '% > 200DMA' },
          ]}
        />
      </Box>
    </Box>
  );
};