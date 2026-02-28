import React, { useState, useMemo } from 'react';
import { Box, Text, HStack, VStack } from '@chakra-ui/react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { SECTOR_PALETTE, STAGE_COLORS } from '../../constants/chart';
import { useChartColors } from '../../hooks/useChartColors';

const COLUMN_LABELS: Record<string, string> = {
  perf_1d: '1D Change %',
  perf_5d: '5D Change %',
  perf_20d: '20D Change %',
  perf_60d: '60D Change %',
  rsi: 'RSI (14)',
  atr_14: 'ATR (14)',
  atrp_14: 'ATR %',
  rs_mansfield_pct: 'RS Mansfield',
  volume_avg_20d: 'Avg Volume (20d)',
  market_cap: 'Market Cap',
  range_pos_52w: '52W Range %',
  pe_ttm: 'P/E (TTM)',
  beta: 'Beta',
  sector: 'Sector',
  stage_label: 'Stage',
  ma_bucket: 'MA Bucket',
};

const NUMERIC_COLUMNS = [
  'perf_1d', 'perf_5d', 'perf_20d', 'perf_60d',
  'rsi', 'atr_14', 'atrp_14', 'rs_mansfield_pct',
  'volume_avg_20d', 'market_cap', 'range_pos_52w', 'pe_ttm', 'beta',
] as const;

const COLOR_COLUMNS = ['stage_label', 'sector', 'ma_bucket'] as const;

const STAGE_HEX: Record<string, string> = {
  '1': '#718096',
  '2A': '#38A169',
  '2B': '#48BB78',
  '2C': '#ECC94B',
  '3': '#ED8936',
  '4': '#E53E3E',
};

const MA_BUCKET_HEX: Record<string, string> = {
  above_all: '#38A169',
  above_50: '#48BB78',
  above_200: '#ECC94B',
  below_all: '#E53E3E',
};

export type BubbleChartProps = {
  data: any[];
  defaultX?: string;
  defaultY?: string;
  defaultColor?: string;
  defaultSize?: string;
};

type DropdownProps = {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (v: string) => void;
};

const Dropdown: React.FC<DropdownProps> = ({ label, value, options, onChange }) => (
  <VStack gap={0} align="start" minW="130px">
    <Text fontSize="10px" fontWeight="semibold" color="fg.muted" textTransform="uppercase" letterSpacing="wide">
      {label}
    </Text>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        width: '100%',
        fontSize: 'var(--chakra-fontSizes-xs)',
        backgroundColor: 'var(--chakra-colors-bg-subtle)',
        border: '1px solid var(--chakra-colors-border-subtle)',
        borderRadius: 'var(--chakra-radii-md)',
        padding: 'var(--chakra-space-2) var(--chakra-space-2)',
        cursor: 'pointer',
      }}
    >
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {COLUMN_LABELS[opt] || opt}
        </option>
      ))}
    </select>
  </VStack>
);

const CustomTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <Box bg="bg.panel" borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} shadow="md" minW="180px">
      <Text fontSize="sm" fontWeight="bold" mb={1}>{d.symbol}</Text>
      <Box display="flex" flexDirection="column" gap="2px">
        <HStack justify="space-between" fontSize="xs">
          <Text color="fg.muted">{COLUMN_LABELS[d._xKey] || d._xKey}</Text>
          <Text fontWeight="medium">{fmtVal(d._xVal)}</Text>
        </HStack>
        <HStack justify="space-between" fontSize="xs">
          <Text color="fg.muted">{COLUMN_LABELS[d._yKey] || d._yKey}</Text>
          <Text fontWeight="medium">{fmtVal(d._yVal)}</Text>
        </HStack>
        {d.sector && (
          <HStack justify="space-between" fontSize="xs">
            <Text color="fg.muted">Sector</Text>
            <Text>{d.sector}</Text>
          </HStack>
        )}
        {d.stage_label && (
          <HStack justify="space-between" fontSize="xs">
            <Text color="fg.muted">Stage</Text>
            <Text>{d.stage_label}</Text>
          </HStack>
        )}
      </Box>
    </Box>
  );
};

const fmtVal = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  if (Math.abs(v) >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 10_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(2);
};

const BubbleChart: React.FC<BubbleChartProps> = ({
  data,
  defaultX = 'perf_1d',
  defaultY = 'rs_mansfield_pct',
  defaultColor = 'stage_label',
  defaultSize = 'market_cap',
}) => {
  const cc = useChartColors();
  const [xKey, setXKey] = useState(defaultX);
  const [yKey, setYKey] = useState(defaultY);
  const [colorKey, setColorKey] = useState(defaultColor);
  const [sizeKey, setSizeKey] = useState(defaultSize);

  const { chartData, colorMap, legendItems } = useMemo(() => {
    const uniqueColorValues = new Set<string>();
    const maxSize = Math.max(
      ...data.map((d) => Math.abs(Number(d[sizeKey]) || 0)),
      1,
    );

    const points = data
      .filter((d) => {
        const xv = Number(d[xKey]);
        const yv = Number(d[yKey]);
        return Number.isFinite(xv) && Number.isFinite(yv);
      })
      .map((d) => {
        const colorVal = String(d[colorKey] ?? 'Unknown');
        uniqueColorValues.add(colorVal);
        const rawSize = Math.abs(Number(d[sizeKey]) || 0);
        const normSize = maxSize > 0 ? (rawSize / maxSize) * 800 + 40 : 100;

        return {
          x: Number(d[xKey]),
          y: Number(d[yKey]),
          z: normSize,
          symbol: d.symbol,
          sector: d.sector,
          stage_label: d.stage_label,
          _colorVal: colorVal,
          _xKey: xKey,
          _yKey: yKey,
          _xVal: Number(d[xKey]),
          _yVal: Number(d[yKey]),
        };
      });

    const cMap: Record<string, string> = {};
    const sortedColorVals = [...uniqueColorValues].sort();
    sortedColorVals.forEach((val, idx) => {
      if (colorKey === 'stage_label') {
        cMap[val] = STAGE_HEX[val] ?? '#718096';
      } else if (colorKey === 'ma_bucket') {
        cMap[val] = MA_BUCKET_HEX[val] ?? '#718096';
      } else {
        cMap[val] = SECTOR_PALETTE[idx % SECTOR_PALETTE.length] as string;
      }
    });

    const legend = sortedColorVals.map((val) => ({
      label: val,
      color: cMap[val],
    }));

    return { chartData: points, colorMap: cMap, legendItems: legend };
  }, [data, xKey, yKey, colorKey, sizeKey]);

  const groupedByColor = useMemo(() => {
    const groups: Record<string, typeof chartData> = {};
    for (const pt of chartData) {
      const key = pt._colorVal;
      if (!groups[key]) groups[key] = [];
      groups[key].push(pt);
    }
    return groups;
  }, [chartData]);

  if (data.length === 0) {
    return (
      <Box p={4} textAlign="center">
        <Text fontSize="sm" color="fg.muted">No data available for bubble chart</Text>
      </Box>
    );
  }

  return (
    <Box>
      <HStack gap={3} flexWrap="wrap" mb={3}>
        <Dropdown label="X Axis" value={xKey} options={NUMERIC_COLUMNS} onChange={setXKey} />
        <Dropdown label="Y Axis" value={yKey} options={NUMERIC_COLUMNS} onChange={setYKey} />
        <Dropdown label="Color" value={colorKey} options={COLOR_COLUMNS} onChange={setColorKey} />
        <Dropdown label="Size" value={sizeKey} options={NUMERIC_COLUMNS} onChange={setSizeKey} />
      </HStack>

      <ResponsiveContainer width="100%" height={420}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={cc.grid} />
          <XAxis
            type="number"
            dataKey="x"
            name={COLUMN_LABELS[xKey] || xKey}
            tick={{ fontSize: 10, fill: cc.muted }}
            tickLine={false}
            axisLine={{ stroke: cc.grid }}
            label={{ value: COLUMN_LABELS[xKey] || xKey, position: 'insideBottom', offset: -18, fontSize: 11, fill: cc.muted }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name={COLUMN_LABELS[yKey] || yKey}
            tick={{ fontSize: 10, fill: cc.muted }}
            tickLine={false}
            axisLine={{ stroke: cc.grid }}
            label={{ value: COLUMN_LABELS[yKey] || yKey, angle: -90, position: 'insideLeft', offset: 5, fontSize: 11, fill: cc.muted }}
          />
          <ZAxis type="number" dataKey="z" range={[30, 600]} />
          <ReferenceLine x={0} stroke={cc.refLine} strokeDasharray="4 3" />
          <ReferenceLine y={0} stroke={cc.refLine} strokeDasharray="4 3" />
          <RTooltip content={<CustomTooltip />} cursor={false} />
          {Object.entries(groupedByColor).map(([colorVal, points]) => (
            <Scatter
              key={colorVal}
              data={points}
              fill={colorMap[colorVal] || '#718096'}
              fillOpacity={0.7}
              stroke={colorMap[colorVal] || '#718096'}
              strokeWidth={1}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>

      {legendItems.length > 0 && legendItems.length <= 20 && (
        <Box display="flex" flexWrap="wrap" gap="6px" mt={2} px={1} justifyContent="center">
          {legendItems.map((item) => (
            <HStack key={item.label} gap={1}>
              <Box w="8px" h="8px" borderRadius="full" flexShrink={0} bg={item.color} />
              <Text fontSize="10px" color="fg.muted">{item.label}</Text>
            </HStack>
          ))}
        </Box>
      )}
    </Box>
  );
};

export default BubbleChart;
