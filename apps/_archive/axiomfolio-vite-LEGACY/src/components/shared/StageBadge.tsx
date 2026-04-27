import React from 'react';

import { Badge } from '@/components/ui/badge';
import { STAGE_SUBTLE_BADGE } from '@/lib/stageTailwind';
import { cn } from '@/lib/utils';
import { STAGE_COLORS } from '../../constants/chart';

export interface StageBadgeProps {
  stage: string;
  size?: 'sm' | 'md';
}

const StageBadge: React.FC<StageBadgeProps> = ({ stage, size = 'sm' }) => {
  const palette = STAGE_COLORS[stage] ?? 'gray';
  const paletteClass = STAGE_SUBTLE_BADGE[palette] ?? STAGE_SUBTLE_BADGE.gray;
  return (
    <Badge
      variant="outline"
      className={cn(
        paletteClass,
        size === 'sm' && 'h-5 px-2 py-0.5 text-[10px]',
        size === 'md' && 'h-6 px-2.5 text-xs'
      )}
      aria-label={`Stage: ${stage || 'unknown'}`}
    >
      {stage || '?'}
    </Badge>
  );
};

export default StageBadge;
