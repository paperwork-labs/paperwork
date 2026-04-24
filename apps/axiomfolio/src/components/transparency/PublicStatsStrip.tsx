import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type PublicStats = {
  portfolios_tracked: number;
  charts_rendered_24h: number;
  brokers_supported: number;
};

async function fetchPublicStats(): Promise<PublicStats> {
  const { data } = await api.get<PublicStats>('/public/stats');
  return data;
}

function useAnimatedInt(target: number, { enabled = true } = {}): number {
  const [value, setValue] = useState(enabled ? 0 : target);
  useEffect(() => {
    if (!enabled) {
      setValue(target);
      return;
    }
    let cancelled = false;
    let raf = 0;
    const start = performance.now();
    const duration = 700;
    const tick = (now: number) => {
      if (cancelled) return;
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - t) ** 3;
      setValue(Math.round(target * eased));
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
  }, [target, enabled]);
  return value;
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() =>
    typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false,
  );
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mql.matches);
    const handler = (e: MediaQueryListEvent) => {
      setReduced(e.matches);
    };
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', handler);
      return () => {
        mql.removeEventListener('change', handler);
      };
    }
    mql.addListener(handler);
    return () => {
      mql.removeListener(handler);
    };
  }, []);
  return reduced;
}

const StatBlock: React.FC<{
  label: string;
  value: number;
  animate: boolean;
}> = ({ label, value, animate }) => {
  const shown = useAnimatedInt(value, { enabled: animate });
  return (
    <div className="flex flex-col items-center gap-1 text-center sm:items-start sm:text-left">
      <p className="font-heading text-3xl font-semibold tabular-nums tracking-tight text-foreground sm:text-4xl">
        {shown.toLocaleString()}
      </p>
      <p className="max-w-[14rem] text-xs text-muted-foreground sm:text-sm">{label}</p>
    </div>
  );
};

const PublicStatsStrip: React.FC<{ className?: string }> = ({ className }) => {
  const prefersReducedMotion = usePrefersReducedMotion();
  const query = useQuery({
    queryKey: ['public', 'stats'],
    queryFn: fetchPublicStats,
    staleTime: 5 * 60 * 1000,
  });

  if (query.isLoading) {
    return (
      <div
        className={cn(
          'grid gap-6 rounded-xl border border-border bg-muted/20 px-6 py-8 sm:grid-cols-3',
          className,
        )}
      >
        {[1, 2, 3].map((k) => (
          <div key={k} className="flex flex-col gap-2">
            <div className="h-9 w-24 animate-pulse rounded-md bg-muted" />
            <div className="h-4 w-32 animate-pulse rounded-md bg-muted" />
          </div>
        ))}
      </div>
    );
  }

  if (query.isError) {
    return (
      <div
        className={cn(
          'rounded-xl border border-destructive/40 bg-destructive/5 px-6 py-6 text-center text-sm text-destructive',
          className,
        )}
        data-testid="public-stats-strip-error"
      >
        Live stats are temporarily unavailable.
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="mt-2 w-full"
          onClick={() => void query.refetch()}
        >
          Retry
        </Button>
      </div>
    );
  }

  if (!query.data) {
    return null;
  }

  const { portfolios_tracked, charts_rendered_24h, brokers_supported } = query.data;

  return (
    <div
      className={cn(
        'grid gap-8 rounded-xl border border-border bg-card px-6 py-8 shadow-sm sm:grid-cols-3',
        className,
      )}
      data-testid="public-stats-strip"
    >
      <StatBlock label="Portfolios tracked" value={portfolios_tracked} animate={!prefersReducedMotion} />
      <StatBlock label="Charts rendered (24h)" value={charts_rendered_24h} animate={!prefersReducedMotion} />
      <StatBlock
        label="Brokers you can connect or import from"
        value={brokers_supported}
        animate={!prefersReducedMotion}
      />
    </div>
  );
};

export default PublicStatsStrip;
