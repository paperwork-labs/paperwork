/**
 * `AllocationTreemap` — recharts Treemap of the user's portfolio allocation.
 *
 * Group rectangles are color-coded from the design-system sector palette
 * (single-source `SECTOR_PALETTE`), keyed by the stable `group.key` so the
 * same sector keeps the same color across renders even when ordering
 * shifts between filters.
 */
import * as React from 'react';
import { ResponsiveContainer, Treemap } from 'recharts';

import { SECTOR_PALETTE } from '@/constants/chart';

import type { AllocationGroup } from '@/hooks/usePortfolioAllocation';

interface AllocationTreemapProps {
  groups: AllocationGroup[];
  height?: number;
  onSelect: (group: AllocationGroup) => void;
}

interface TreeNode extends Record<string, unknown> {
  name: string;
  size: number;
  fill: string;
  percentage: number;
  groupKey: string;
}

function buildNodes(groups: AllocationGroup[]): TreeNode[] {
  return groups.map((g, i) => ({
    name: g.label,
    size: g.total_value,
    // `g.total_value` is already absolute exposure on the backend, so any
    // zero/negative entry would be a backend contract violation -- recharts
    // would still try to render it as an invisible rectangle. Drop them
    // here rather than feeding them into the chart.
    fill: SECTOR_PALETTE[i % SECTOR_PALETTE.length],
    percentage: g.percentage,
    groupKey: g.key,
  }));
}

const Cell: React.FC<{
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  payload?: TreeNode;
  fill?: string;
  onSelect?: (key: string) => void;
}> = (props) => {
  const { x = 0, y = 0, width = 0, height = 0, payload, name, fill = '#475569', onSelect } = props;
  if (width <= 0 || height <= 0) return null;
  const showLabel = width > 60 && height > 32;
  const showPct = width > 60 && height > 56;
  const groupKey = payload?.groupKey;
  const pct = payload?.percentage;
  const handleClick = () => {
    if (groupKey && onSelect) onSelect(groupKey);
  };
  return (
    <g
      role="button"
      tabIndex={groupKey ? 0 : -1}
      aria-label={`${name}, ${pct?.toFixed(1)} percent of portfolio`}
      onClick={handleClick}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && groupKey && onSelect) {
          e.preventDefault();
          onSelect(groupKey);
        }
      }}
      style={{ cursor: groupKey ? 'pointer' : 'default', outline: 'none' }}
    >
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={fill}
        stroke="rgba(0,0,0,0.18)"
        strokeWidth={1}
      />
      {showLabel && (
        <text
          x={x + width / 2}
          y={y + height / 2 - (showPct ? 8 : 0)}
          textAnchor="middle"
          fill="#FFFFFF"
          fontSize={Math.min(14, Math.max(10, Math.sqrt(width * height) / 8))}
          fontWeight={600}
          style={{ textShadow: '0 1px 2px rgba(0,0,0,0.45)' }}
        >
          {name}
        </text>
      )}
      {showPct && pct !== undefined && (
        <text
          x={x + width / 2}
          y={y + height / 2 + 10}
          textAnchor="middle"
          fill="rgba(255,255,255,0.92)"
          fontSize={11}
          style={{ textShadow: '0 1px 2px rgba(0,0,0,0.45)' }}
        >
          {pct.toFixed(1)}%
        </text>
      )}
    </g>
  );
};

export function AllocationTreemap({ groups, height = 420, onSelect }: AllocationTreemapProps) {
  const nodes = React.useMemo(() => buildNodes(groups), [groups]);

  // Recharts' `<Treemap content>` prop receives a clone of the node, but the
  // payload it forwards to a function-component is keyed off the chart's
  // internal layout, not our source. We pass `onSelect` via closure rather
  // than props so the cell renderer always sees the latest handler.
  const renderCell = React.useCallback(
    (cellProps: any) => (
      <Cell
        {...cellProps}
        onSelect={(key: string) => {
          const found = groups.find((g) => g.key === key);
          if (found) onSelect(found);
        }}
      />
    ),
    [groups, onSelect],
  );

  return (
    <div
      role="figure"
      aria-label="Portfolio allocation treemap"
      className="w-full"
      style={{ height }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <Treemap
          data={nodes}
          dataKey="size"
          nameKey="name"
          stroke="none"
          isAnimationActive={false}
          content={renderCell as any}
        />
      </ResponsiveContainer>
    </div>
  );
}

export default AllocationTreemap;
