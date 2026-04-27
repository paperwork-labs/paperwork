import React from 'react';

import { Card, CardContent } from '@/components/ui/card';
import { Skeleton as ShadcnSkeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

/** Matches StatCard dimensions with pulsing placeholder. */
export const StatCardSkeleton: React.FC = () => (
  <Card size="sm" className="gap-0 border border-border py-0 shadow-none ring-0">
    <CardContent className="space-y-2 px-4 py-4">
      <ShadcnSkeleton className="h-3.5 w-[60%]" />
      <ShadcnSkeleton className="h-6 w-[80%]" />
    </CardContent>
  </Card>
);

/** Rows of pulsing bars matching table column widths. */
export const TableSkeleton: React.FC<{ rows?: number; cols?: number }> = ({ rows = 8, cols = 5 }) => (
  <div className="flex flex-col gap-2" data-testid="table-skeleton">
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="flex gap-3">
        {Array.from({ length: cols }).map((_, j) => (
          <ShadcnSkeleton
            key={j}
            className={cn('h-5', j === 0 ? 'min-w-0 flex-[2]' : 'min-w-0 flex-1')}
          />
        ))}
      </div>
    ))}
  </div>
);

/** Rectangle with pulsing gradient for chart placeholders. */
export const ChartSkeleton: React.FC = () => (
  <div className="min-h-[200px] overflow-hidden rounded-lg bg-muted">
    <ShadcnSkeleton className="h-[200px] w-full rounded-lg" />
  </div>
);
