import React, { useState, useMemo } from 'react';
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

import { cn } from '@/lib/utils';

import { SECTOR_PALETTE, STAGE_HEX } from '../../constants/chart';
import { useChartColors } from '../../hooks/useChartColors';
import { useColorMode } from '../../theme/colorMode';

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
  onSymbolClick?: (symbol: string) => void;
};

type DropdownProps = {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (v: string) => void;
};

const Dropdown: React.FC<DropdownProps> = ({ label, value, options, onChange }) => (
  <div className="flex min-w-[130px] flex-col items-start gap-0">
    <span className="text-[10px] font-semibold tracking-wide text-muted-foreground uppercase">
      {label}
    </span>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        'mt-0.5 w-full cursor-pointer rounded-md border border-border bg-muted px-2 py-2 text-xs',
        'text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none'
      )}
    >
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {COLUMN_LABELS[opt] || opt}
        </option>
      ))}
    </select>
  </div>
);

const CustomTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div
      className={cn(
        'min-w-[180px] rounded-lg border border-border bg-popover p-3 text-popover-foreground shadow-md'
      )}
    >
      <div className="mb-1 text-sm font-bold">{d.symbol}</div>
      <div className="flex flex-col gap-0.5">
        <div className="flex justify-between gap-2 text-xs">
          <span className="text-muted-foreground">{COLUMN_LABELS[d._xKey] || d._xKey}</span>
          <span className="font-medium">{fmtVal(d._xVal)}</span>
        </div>
        <div className="flex justify-between gap-2 text-xs">
          <span className="text-muted-foreground">{COLUMN_LABELS[d._yKey] || d._yKey}</span>
          <span className="font-medium">{fmtVal(d._yVal)}</span>
        </div>
        {d.sector && (
          <div className="flex justify-between gap-2 text-xs">
            <span className="text-muted-foreground">Sector</span>
            <span>{d.sector}</span>
          </div>
        )}
        {d.stage_label && (
          <div className="flex justify-between gap-2 text-xs">
            <span className="text-muted-foreground">Stage</span>
            <span>{d.stage_label}</span>
          </div>
        )}
      </div>
    </div>
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
  onSymbolClick,
}) => {
  const cc = useChartColors();
  const { colorMode } = useColorMode();
  const darkIdx = colorMode === 'dark' ? 1 : 0;
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
        const hex = STAGE_HEX[val];
        cMap[val] = hex ? hex[darkIdx] : '#718096';
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
  }, [data, xKey, yKey, colorKey, sizeKey, darkIdx]);

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
      <div className="p-4 text-center">
        <p className="text-sm text-muted-foreground">No data available for bubble chart</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-3">
        <Dropdown label="X Axis" value={xKey} options={NUMERIC_COLUMNS} onChange={setXKey} />
        <Dropdown label="Y Axis" value={yKey} options={NUMERIC_COLUMNS} onChange={setYKey} />
        <Dropdown label="Color" value={colorKey} options={COLOR_COLUMNS} onChange={setColorKey} />
        <Dropdown label="Size" value={sizeKey} options={NUMERIC_COLUMNS} onChange={setSizeKey} />
      </div>

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
              cursor={onSymbolClick ? 'pointer' : undefined}
              onClick={onSymbolClick ? (entry: any) => { if (entry?.symbol) onSymbolClick(entry.symbol); } : undefined}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>

      {legendItems.length > 0 && legendItems.length <= 20 && (
        <div className="mt-2 flex flex-wrap justify-center gap-1.5 px-1">
          {legendItems.map((item) => (
            <div key={item.label} className="flex items-center gap-1">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-[10px] text-muted-foreground">{item.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default BubbleChart;
