import React, { useMemo } from 'react';
import { ResponsiveContainer, Treemap, Tooltip as RechartsTooltip } from 'recharts';

import { cn } from '@/lib/utils';

import { heatMapColor, HEAT_MAP_LEGEND } from '../../constants/chart';

export interface FinvizData {
  name: string;
  size: number;
  change: number;
  sector: string;
  value: number;
}

interface FinvizHeatMapProps {
  data: FinvizData[];
  height?: number;
  showLegend?: boolean;
  title?: string;
}

/** Recharts Treemap expects index signature on data nodes. */
interface TreeNode extends Record<string, unknown> {
  name: string;
  color?: string;
  change?: number;
  value?: number;
  sector?: string;
  size?: number;
  children?: TreeNode[];
}

function buildSectorTree(data: FinvizData[]): TreeNode[] {
  const sectors = new Map<string, TreeNode[]>();
  for (const d of data) {
    const key = d.sector || 'Other';
    if (!sectors.has(key)) sectors.set(key, []);
    sectors.get(key)!.push({
      name: d.name,
      size: d.size,
      color: heatMapColor(d.change),
      change: d.change,
      value: d.value,
      sector: d.sector,
    });
  }
  return Array.from(sectors.entries())
    .map(([name, children]) => ({ name, children }))
    .sort((a, b) => {
      const sumA = a.children.reduce((s, c) => s + (c.size ?? 0), 0);
      const sumB = b.children.reduce((s, c) => s + (c.size ?? 0), 0);
      return sumB - sumA;
    });
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  if (!d || d.change == null) return null;
  return (
    <div
      className={cn(
        'rounded-md border border-border bg-popover p-3 text-sm text-popover-foreground shadow-lg'
      )}
    >
      <div className="font-bold text-foreground">{d.name}</div>
      {d.value != null && (
        <div className="text-muted-foreground">Value: ${d.value.toLocaleString()}</div>
      )}
      <div
        className={cn(
          d.change >= 0 ? 'text-[rgb(var(--status-success))]' : 'text-[rgb(var(--status-danger))]'
        )}
      >
        {d.change >= 0 ? '+' : ''}{d.change.toFixed(2)}%
      </div>
      {d.sector && <div className="text-xs text-muted-foreground">{d.sector}</div>}
    </div>
  );
};

const CellContent: React.FC<any> = (props) => {
  const { x, y, width, height, depth, name, color, change } = props;

  if (width <= 0 || height <= 0) return null;

  // depth 1 = sector group, depth 2 = individual ticker
  if (depth === 1) {
    const showLabel = width > 50 && height > 14;
    return (
      <g>
        <rect x={x} y={y} width={width} height={height} fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth={2} />
        {showLabel && (
          <text
            x={x + 4}
            y={y + 12}
            fill="rgba(255,255,255,0.6)"
            fontSize={10}
            fontWeight="600"
          >
            {name}
          </text>
        )}
      </g>
    );
  }

  if (depth === 2) {
    const fill = color || '#475569';
    const area = width * height;
    const fontSize = Math.max(8, Math.min(14, Math.sqrt(area) / 5));
    const showTicker = width > 32 && height > 18;
    const showPct = width > 32 && height > 32;

    return (
      <g>
        <rect x={x} y={y} width={width} height={height} fill={fill} stroke="rgba(0,0,0,0.15)" strokeWidth={1} />
        {showTicker && (
          <text
            x={x + width / 2}
            y={y + height / 2 + (showPct ? -fontSize * 0.35 : fontSize * 0.35)}
            textAnchor="middle"
            fill="#fff"
            fontSize={fontSize}
            fontWeight="bold"
            style={{ textShadow: '0 1px 2px rgba(0,0,0,0.5)' }}
          >
            {name}
          </text>
        )}
        {showPct && change != null && (
          <text
            x={x + width / 2}
            y={y + height / 2 + fontSize * 0.85}
            textAnchor="middle"
            fill="rgba(255,255,255,0.85)"
            fontSize={Math.max(7, fontSize - 1.5)}
            style={{ textShadow: '0 1px 2px rgba(0,0,0,0.5)' }}
          >
            {change > 0 ? '+' : ''}{change.toFixed(1)}%
          </text>
        )}
      </g>
    );
  }

  return null;
};

const FinvizHeatMap: React.FC<FinvizHeatMapProps> = ({
  data,
  height = 300,
  showLegend = true,
  title = 'Portfolio Heat Map',
}) => {
  const treeData = useMemo(() => buildSectorTree(data), [data]);

  if (!data.length) return null;

  return (
    <div className="flex flex-col items-stretch gap-3">
      {title ? <h3 className="text-base font-semibold text-foreground">{title}</h3> : null}

      <div className="overflow-hidden rounded-md border border-border bg-card">
        <ResponsiveContainer width="100%" height={height}>
          <Treemap
            data={treeData}
            dataKey="size"
            stroke="none"
            content={<CellContent />}
            isAnimationActive={false}
          >
            <RechartsTooltip content={<CustomTooltip />} />
          </Treemap>
        </ResponsiveContainer>
      </div>

      {showLegend && (
        <div className="flex flex-wrap justify-center gap-1 text-xs">
          {HEAT_MAP_LEGEND.map((stop) => (
            <div key={stop.label} className="flex items-center gap-1">
              <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: stop.hex }} />
              <span className="text-muted-foreground">{stop.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FinvizHeatMap;
