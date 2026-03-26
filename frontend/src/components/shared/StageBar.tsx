import React from 'react';

import { Badge } from '@/components/ui/badge';
import { STAGE_BAR_FILL, STAGE_SOLID_BADGE, STAGE_SUBTLE_BADGE } from '@/lib/stageTailwind';
import { cn } from '@/lib/utils';
import { STAGE_COLORS } from '../../constants/chart';

/** Display order: 10 sub-stages, then legacy rollup labels (1–4) for older snapshot data. */
const STAGES = [
  '1A', '1B', '2A', '2B', '2B(RS-)', '2C', '3A', '3B', '4A', '4B', '4C',
  '1', '2', '3', '4',
] as const;

export interface StageBarProps {
  counts: Record<string, number>;
  total?: number;
  onClick?: (stage: string) => void;
  activeStage?: string | null;
}

const StageBar: React.FC<StageBarProps> = ({ counts, total: totalProp, onClick, activeStage }) => {
  const total = totalProp ?? Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) {
    return <p className="text-xs text-muted-foreground">No data</p>;
  }
  const isInteractive = !!onClick;
  const distributionLabel = `Stage distribution: ${STAGES.map((s) => `${s}: ${counts[s] ?? 0}`).join(', ')}`;
  return (
    <div>
      <div
        className="flex h-6 overflow-hidden rounded-md"
        role="group"
        aria-label={distributionLabel}
      >
        {STAGES.map((s) => {
          const count = counts[s] ?? 0;
          const pct = (count / total) * 100;
          if (pct === 0) return null;
          const palette = STAGE_COLORS[s] ?? 'gray';
          const fillClass = STAGE_BAR_FILL[palette] ?? STAGE_BAR_FILL.gray;
          const isActive = activeStage === s;
          return (
            <div
              key={s}
              className={cn(
                'flex items-center justify-center',
                fillClass,
                isInteractive && 'cursor-pointer transition-opacity duration-200 hover:opacity-[0.85]',
                activeStage && !isActive && 'opacity-45'
              )}
              style={{ width: `${pct}%` }}
              aria-label={`Stage ${s}: ${count} positions, ${pct.toFixed(0)}%`}
              onClick={isInteractive ? () => onClick(s) : undefined}
              onKeyDown={
                isInteractive
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onClick(s);
                      }
                    }
                  : undefined
              }
              role={isInteractive ? 'button' : undefined}
              tabIndex={isInteractive ? 0 : undefined}
            >
              {pct > 4 && (
                <span className="text-[10px] font-bold text-white">{s}</span>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-1 flex flex-wrap gap-2">
        {STAGES.map((s) => {
          const count = counts[s] ?? 0;
          const palette = STAGE_COLORS[s] ?? 'gray';
          const subtle = STAGE_SUBTLE_BADGE[palette] ?? STAGE_SUBTLE_BADGE.gray;
          const solid = STAGE_SOLID_BADGE[palette] ?? STAGE_SOLID_BADGE.gray;
          const isActive = activeStage === s;
          return (
            <Badge
              key={s}
              variant="outline"
              className={cn(
                'h-5 cursor-default px-2 py-0.5 text-[10px] transition-all duration-200',
                isActive ? solid : subtle,
                isInteractive && 'cursor-pointer'
              )}
              onClick={isInteractive ? () => onClick(s) : undefined}
            >
              {s}: {count} ({total > 0 ? ((count / total) * 100).toFixed(0) : 0}%)
            </Badge>
          );
        })}
      </div>
    </div>
  );
};

export default StageBar;
