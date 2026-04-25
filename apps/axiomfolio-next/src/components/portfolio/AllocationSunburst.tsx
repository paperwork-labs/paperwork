/**
 * `AllocationSunburst` — hand-rolled SVG sunburst (donut) for allocation.
 *
 * Recharts ships `Pie` but no first-class sunburst, and pulling in another
 * dep (`d3-hierarchy` etc.) is a non-starter for a single new visualization
 * (we already ship recharts; budget rule per the v1 sprint plan).
 *
 * Visual model: a single ring whose slice angles are proportional to the
 * group's `total_value`. The two-ring "group + holding" sunburst is reserved
 * for a follow-up; the page already exposes per-group drill-down via the
 * shared dialog so the immediate UX gap is closed.
 */
import * as React from 'react';

import { SECTOR_PALETTE } from '@/constants/chart';

import type { AllocationGroup } from '@/hooks/usePortfolioAllocation';

interface AllocationSunburstProps {
  groups: AllocationGroup[];
  height?: number;
  onSelect: (group: AllocationGroup) => void;
}

interface Slice {
  group: AllocationGroup;
  startAngle: number;
  endAngle: number;
  fill: string;
}

function describeArc(
  cx: number,
  cy: number,
  innerR: number,
  outerR: number,
  startAngle: number,
  endAngle: number,
): string {
  // SVG arc paths can't draw a full 360° sweep in a single arc command;
  // splitting into two halves keeps the donut renderable when a single
  // group dominates the whole portfolio.
  const sweep = endAngle - startAngle;
  if (sweep >= Math.PI * 2 - 1e-6) {
    const halfA = describeArc(cx, cy, innerR, outerR, startAngle, startAngle + Math.PI);
    const halfB = describeArc(cx, cy, innerR, outerR, startAngle + Math.PI, startAngle + 2 * Math.PI);
    return `${halfA} ${halfB}`;
  }
  const x1 = cx + outerR * Math.cos(startAngle);
  const y1 = cy + outerR * Math.sin(startAngle);
  const x2 = cx + outerR * Math.cos(endAngle);
  const y2 = cy + outerR * Math.sin(endAngle);
  const x3 = cx + innerR * Math.cos(endAngle);
  const y3 = cy + innerR * Math.sin(endAngle);
  const x4 = cx + innerR * Math.cos(startAngle);
  const y4 = cy + innerR * Math.sin(startAngle);
  const largeArc = sweep > Math.PI ? 1 : 0;
  return [
    `M ${x1} ${y1}`,
    `A ${outerR} ${outerR} 0 ${largeArc} 1 ${x2} ${y2}`,
    `L ${x3} ${y3}`,
    `A ${innerR} ${innerR} 0 ${largeArc} 0 ${x4} ${y4}`,
    'Z',
  ].join(' ');
}

export function AllocationSunburst({ groups, height = 420, onSelect }: AllocationSunburstProps) {
  const total = React.useMemo(
    () => groups.reduce((sum, g) => sum + (g.total_value > 0 ? g.total_value : 0), 0),
    [groups],
  );

  const slices = React.useMemo<Slice[]>(() => {
    if (total <= 0) return [];
    let cursor = -Math.PI / 2; // 12 o'clock start
    return groups
      .filter((g) => g.total_value > 0)
      .map((g, i) => {
        const sweep = (g.total_value / total) * Math.PI * 2;
        const slice: Slice = {
          group: g,
          startAngle: cursor,
          endAngle: cursor + sweep,
          fill: SECTOR_PALETTE[i % SECTOR_PALETTE.length],
        };
        cursor += sweep;
        return slice;
      });
  }, [groups, total]);

  const size = height;
  const cx = size / 2;
  const cy = size / 2;
  const outerR = (size / 2) * 0.92;
  const innerR = outerR * 0.55;

  if (slices.length === 0) {
    return (
      <div
        role="figure"
        aria-label="Portfolio allocation sunburst"
        className="flex w-full items-center justify-center text-muted-foreground"
        style={{ height }}
      >
        No allocation to display.
      </div>
    );
  }

  return (
    <div
      role="figure"
      aria-label="Portfolio allocation sunburst"
      className="flex w-full items-center justify-center"
      style={{ height }}
    >
      <svg
        viewBox={`0 0 ${size} ${size}`}
        width={size}
        height={size}
        role="img"
        aria-label="Portfolio allocation by group"
      >
        {slices.map((s) => {
          const midAngle = (s.startAngle + s.endAngle) / 2;
          const labelR = (innerR + outerR) / 2;
          const lx = cx + labelR * Math.cos(midAngle);
          const ly = cy + labelR * Math.sin(midAngle);
          const sweep = s.endAngle - s.startAngle;
          // Hide labels on slivers — the tooltip handles those.
          const showLabel = sweep > 0.2;
          return (
            <g
              key={s.group.key}
              role="button"
              tabIndex={0}
              aria-label={`${s.group.label}, ${s.group.percentage.toFixed(1)} percent`}
              onClick={() => onSelect(s.group)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelect(s.group);
                }
              }}
              style={{ cursor: 'pointer', outline: 'none' }}
            >
              <path
                d={describeArc(cx, cy, innerR, outerR, s.startAngle, s.endAngle)}
                fill={s.fill}
                stroke="rgba(0,0,0,0.18)"
                strokeWidth={1}
              />
              {showLabel && (
                <text
                  x={lx}
                  y={ly}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill="#FFFFFF"
                  fontSize={11}
                  fontWeight={600}
                  style={{ textShadow: '0 1px 2px rgba(0,0,0,0.45)' }}
                >
                  {s.group.label}
                </text>
              )}
            </g>
          );
        })}
        <text
          x={cx}
          y={cy - 8}
          textAnchor="middle"
          fill="currentColor"
          className="fill-foreground"
          fontSize={12}
        >
          Total
        </text>
        <text
          x={cx}
          y={cy + 12}
          textAnchor="middle"
          fill="currentColor"
          className="fill-foreground"
          fontSize={16}
          fontWeight={600}
        >
          ${total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </text>
      </svg>
    </div>
  );
}

export default AllocationSunburst;
