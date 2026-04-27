import React from 'react';
import { Loader2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

export const PortfolioSummarySkeleton: React.FC = () => {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(250px,1fr))] gap-6">
      {[1, 2, 3, 4].map((i) => (
        <Card key={i}>
          <CardContent className="space-y-3 pt-6">
            <Skeleton className="h-5 w-3/5" />
            <Skeleton className="h-8 w-4/5" />
            <div className="flex items-center gap-2">
              <Skeleton className="size-8 rounded-full" />
              <Skeleton className="h-4 w-2/5" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};

export const HoldingsTableSkeleton: React.FC<{ rows?: number }> = ({ rows = 10 }) => {
  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <div className="flex justify-between">
          <Skeleton className="h-6 w-[150px]" />
          <Skeleton className="h-8 w-[200px]" />
        </div>

        <div className="flex gap-4 py-2">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-14" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-14" />
        </div>

        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex gap-4 border-b border-border py-3 last:border-0">
            <Skeleton className="size-8 shrink-0 rounded-full" />
            <div className="flex flex-1 flex-col gap-1">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-3 w-12" />
            </div>
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-16" />
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

export const TransactionsSkeleton: React.FC<{ rows?: number }> = ({ rows = 15 }) => {
  return (
    <Card>
      <CardContent className="space-y-3 pt-6">
        <div className="mb-4 flex gap-4">
          <Skeleton className="h-8 w-[150px]" />
          <Skeleton className="h-8 w-[120px]" />
          <Skeleton className="h-8 w-[100px]" />
        </div>

        {Array.from({ length: rows }).map((_, i) => (
          <div
            key={i}
            className="flex justify-between gap-3 rounded-lg border border-border p-3"
          >
            <div className="flex items-center gap-3">
              <Skeleton className="size-6 rounded-full" />
              <div className="flex flex-col gap-1">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-3 w-28" />
              </div>
            </div>
            <div className="flex flex-col items-end gap-1">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-3 w-12" />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

export const OptionsPortfolioSkeleton: React.FC = () => {
  return (
    <div className="flex flex-col gap-6">
      <PortfolioSummarySkeleton />

      <Card>
        <CardContent className="space-y-4 pt-6">
          <Skeleton className="h-6 w-[200px]" />

          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="rounded-md border border-border bg-muted/30 p-4">
              <div className="mb-3 flex justify-between">
                <div className="flex flex-col gap-1">
                  <Skeleton className="h-[18px] w-24" />
                  <Skeleton className="h-3.5 w-36" />
                </div>
                <div className="flex flex-col items-end gap-1">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-3.5 w-16" />
                </div>
              </div>

              <div className="grid grid-cols-4 gap-4">
                <Skeleton className="h-3" />
                <Skeleton className="h-3" />
                <Skeleton className="h-3" />
                <Skeleton className="h-3" />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
};

export const TaxLotsSkeleton: React.FC = () => {
  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardContent className="pt-6">
          <div className="flex justify-between">
            <div className="flex flex-col gap-2">
              <Skeleton className="h-5 w-28" />
              <Skeleton className="h-8 w-24" />
            </div>
            <div className="flex flex-col items-end gap-2">
              <Skeleton className="h-5 w-36" />
              <Skeleton className="h-8 w-28" />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-4 pt-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="rounded-md border border-border bg-muted/30 p-4">
              <div className="mb-3 flex justify-between">
                <div className="flex items-center gap-3">
                  <Skeleton className="size-10 rounded-full" />
                  <div className="flex flex-col gap-1">
                    <Skeleton className="h-[18px] w-16" />
                    <Skeleton className="h-3.5 w-20" />
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-3.5 w-16" />
                </div>
              </div>

              <div className="grid grid-cols-5 gap-4">
                {[0, 1, 2, 3, 4].map((j) => (
                  <div key={j} className="flex flex-col gap-1">
                    <Skeleton className="h-3 w-10" />
                    <Skeleton className="h-4 w-14" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
};

export const LoadingSpinner: React.FC<{
  message?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showProgress?: boolean;
  progress?: number;
}> = ({ message = 'Loading...', size = 'lg', showProgress = false, progress = 0 }) => {
  const iconClass = cn(
    'text-primary',
    size === 'sm' && 'size-4',
    size === 'md' && 'size-6',
    size === 'lg' && 'size-8',
    size === 'xl' && 'size-10',
  );
  return (
    <div className="flex min-h-[200px] flex-col items-center justify-center px-6 py-12">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className={cn('animate-spin', iconClass)} aria-hidden />
        <p className="text-center text-lg text-muted-foreground">{message}</p>
        {showProgress && (
          <div className="w-[200px]">
            <Progress value={progress} max={100} />
            <p className="mt-1 text-center text-sm text-muted-foreground">{progress}%</p>
          </div>
        )}
      </div>
    </div>
  );
};

export const LoadingOverlay: React.FC<{
  message?: string;
  isVisible: boolean;
}> = ({ message = 'Loading...', isVisible }) => {
  if (!isVisible) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-background/92 backdrop-blur-sm"
      role="status"
      aria-live="polite"
    >
      <LoadingSpinner message={message} size="xl" />
    </div>
  );
};

export const MiniSpinner: React.FC<{ size?: 'sm' | 'md' | 'lg' | 'xl' }> = ({ size = 'sm' }) => {
  const iconClass =
    size === 'sm'
      ? 'size-3.5'
      : size === 'md'
        ? 'size-4'
        : size === 'lg'
          ? 'size-5'
          : 'size-6';
  return <Loader2 className={cn('animate-spin text-current', iconClass)} aria-hidden />;
};

export default {
  PortfolioSummarySkeleton,
  HoldingsTableSkeleton,
  TransactionsSkeleton,
  OptionsPortfolioSkeleton,
  TaxLotsSkeleton,
  LoadingSpinner,
  LoadingOverlay,
  MiniSpinner,
};
