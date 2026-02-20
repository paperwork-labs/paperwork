import React from 'react';
import { Badge } from '@chakra-ui/react';
import { STAGE_COLORS } from '../../constants/chart';

export interface StageBadgeProps {
  stage: string;
  size?: 'sm' | 'md';
}

const StageBadge: React.FC<StageBadgeProps> = ({ stage, size = 'sm' }) => {
  const palette = STAGE_COLORS[stage] ?? 'gray';
  return (
    <Badge
      size={size}
      variant="subtle"
      colorPalette={palette}
      fontSize="xs"
      aria-label={`Stage: ${stage || 'unknown'}`}
    >
      {stage || '?'}
    </Badge>
  );
};

export default StageBadge;
