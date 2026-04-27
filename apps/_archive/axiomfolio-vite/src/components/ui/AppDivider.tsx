import React from 'react';

import { cn } from '@/lib/utils';

export type AppDividerProps = {
  className?: string;
  orientation?: 'horizontal' | 'vertical';
};

/**
 * Horizontal or vertical rule using Tailwind; replaces the former Chakra Separator wrapper.
 */
export function AppDivider({ className, orientation = 'horizontal' }: AppDividerProps) {
  if (orientation === 'vertical') {
    return (
      <div
        role="separator"
        aria-orientation="vertical"
        className={cn('mx-1 h-full w-px shrink-0 self-stretch bg-border', className)}
      />
    );
  }
  return <hr className={cn('shrink-0 border-0 border-t border-border', className)} />;
}

export default AppDivider;
