import React from 'react';
import { AlertTriangle } from 'lucide-react';

import { useQuadState } from '../../hooks/useQuadState';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const QUAD_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  '1': { bg: 'bg-emerald-500/15', text: 'text-emerald-600 dark:text-emerald-400', label: 'Quad 1 — Growth Up, Inflation Down' },
  '2': { bg: 'bg-amber-500/15', text: 'text-amber-600 dark:text-amber-400', label: 'Quad 2 — Growth Up, Inflation Up' },
  '3': { bg: 'bg-red-500/15', text: 'text-red-600 dark:text-red-400', label: 'Quad 3 — Growth Down, Inflation Up' },
  '4': { bg: 'bg-blue-500/15', text: 'text-blue-600 dark:text-blue-400', label: 'Quad 4 — Growth Down, Inflation Down' },
};

function quadMeta(quad: string | null | undefined) {
  if (!quad) return { bg: 'bg-muted', text: 'text-muted-foreground', label: 'Unknown' };
  const key = quad.replace(/\D/g, '');
  return QUAD_COLORS[key] ?? { bg: 'bg-muted', text: 'text-muted-foreground', label: quad };
}

const QuadStatusBar: React.FC = () => {
  const { data, isPending } = useQuadState();
  const quad = data?.quad;

  if (isPending || !quad) return null;

  const operative = quadMeta(quad.operative_quad);
  const quarterly = quadMeta(quad.quarterly_quad);
  const monthly = quadMeta(quad.monthly_quad);

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-border px-4 py-2.5',
        operative.bg,
      )}
    >
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground">Operative Quad</span>
        <Badge className={cn('border-0 font-semibold', operative.bg, operative.text)}>
          {quad.operative_quad || '—'}
        </Badge>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Quarterly</span>
        <Badge variant="outline" className={cn('font-normal', quarterly.text)}>
          {quad.quarterly_quad || '—'}
        </Badge>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Monthly</span>
        <Badge variant="outline" className={cn('font-normal', monthly.text)}>
          {quad.monthly_quad || '—'}
        </Badge>
      </div>

      {quad.divergence_flag && (
        <div className="flex items-center gap-1.5">
          <AlertTriangle className="size-3.5 text-amber-500" />
          <span className="text-xs font-medium text-amber-600 dark:text-amber-400">
            Divergence ({quad.divergence_months ?? '?'}mo)
          </span>
        </div>
      )}

      {quad.as_of_date && (
        <span className="ml-auto text-[10px] text-muted-foreground">
          As of {quad.as_of_date}
        </span>
      )}
    </div>
  );
};

export default QuadStatusBar;
