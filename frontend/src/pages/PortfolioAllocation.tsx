/**
 * `/portfolio/allocation` — interactive allocation explorer.
 *
 * Renders the user's open positions as a treemap or sunburst, switchable
 * between three groupings (sector / asset class / account). Clicking a
 * group opens a drill-down dialog listing the underlying holdings and
 * their per-portfolio weight.
 *
 * Loading / error / empty / data states are kept distinct per
 * `no-silent-fallback.mdc`. Animation honors `prefers-reduced-motion` via
 * the design-system primitives we compose here.
 */
import * as React from 'react';
import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { ChartGlassCard } from '@/components/ui/ChartGlassCard';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { SegmentedPeriodSelector } from '@/components/ui/SegmentedPeriodSelector';
import { TreemapSkeleton } from '@/components/charts/skeletons/TreemapSkeleton';

import {
  AllocationGroup,
  AllocationGroupBy,
  usePortfolioAllocation,
} from '@/hooks/usePortfolioAllocation';

import AllocationTreemap from '@/components/portfolio/AllocationTreemap';
import AllocationSunburst from '@/components/portfolio/AllocationSunburst';

type ViewMode = 'treemap' | 'sunburst';

const VIEW_OPTIONS = [
  { value: 'treemap', label: 'Treemap', ariaLabel: 'View as treemap' },
  { value: 'sunburst', label: 'Sunburst', ariaLabel: 'View as sunburst' },
] as const;

const GROUP_OPTIONS = [
  { value: 'sector', label: 'Sector', ariaLabel: 'Group by sector' },
  { value: 'asset_class', label: 'Asset class', ariaLabel: 'Group by asset class' },
  { value: 'account', label: 'Account', ariaLabel: 'Group by account' },
] as const;

function formatCurrency(value: number): string {
  return value.toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });
}

export default function PortfolioAllocation() {
  const [view, setView] = React.useState<ViewMode>('treemap');
  const [groupBy, setGroupBy] = React.useState<AllocationGroupBy>('sector');
  const [selected, setSelected] = React.useState<AllocationGroup | null>(null);

  const query = usePortfolioAllocation(groupBy);

  const renderBody = () => {
    if (query.isLoading) {
      return <TreemapSkeleton height={420} label="portfolio allocation" />;
    }
    if (query.isError) {
      return (
        <div
          role="alert"
          className="flex h-[420px] flex-col items-center justify-center gap-3 rounded-lg border border-destructive/40 bg-destructive/5 text-center"
        >
          <p className="text-sm text-destructive">Could not load allocation.</p>
          <Button variant="outline" onClick={() => query.refetch()}>
            Retry
          </Button>
        </div>
      );
    }
    const data = query.data;
    if (!data || data.groups.length === 0) {
      return (
        <div className="flex h-[420px] flex-col items-center justify-center gap-3 rounded-lg border border-border/40 bg-card/40 text-center">
          <p className="text-sm text-muted-foreground">
            Nothing to allocate yet — connect a broker to see your portfolio breakdown.
          </p>
          <Button asChild>
            <Link to="/connect">Connect a broker</Link>
          </Button>
        </div>
      );
    }
    if (view === 'sunburst') {
      return (
        <AllocationSunburst
          groups={data.groups}
          height={420}
          onSelect={setSelected}
        />
      );
    }
    return (
      <AllocationTreemap groups={data.groups} height={420} onSelect={setSelected} />
    );
  };

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-foreground">Portfolio allocation</h1>
        <p className="text-sm text-muted-foreground">
          Interactive breakdown of your holdings by sector, asset class, or account.
        </p>
      </header>

      <ChartGlassCard
        as="section"
        ariaLabel="Portfolio allocation chart"
        padding="md"
        level="resting"
      >
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <SegmentedPeriodSelector
              options={GROUP_OPTIONS}
              value={groupBy}
              onChange={(v) => setGroupBy(v as AllocationGroupBy)}
              ariaLabel="Allocation grouping"
              size="sm"
            />
            <SegmentedPeriodSelector
              options={VIEW_OPTIONS}
              value={view}
              onChange={(v) => setView(v as ViewMode)}
              ariaLabel="Visualization mode"
              size="sm"
            />
          </div>
          {query.data && query.data.total_value > 0 && (
            <div className="text-right text-xs text-muted-foreground">
              <span className="block">Total exposure</span>
              <span className="text-base font-semibold text-foreground">
                {formatCurrency(query.data.total_value)}
              </span>
            </div>
          )}
        </div>
        {renderBody()}
      </ChartGlassCard>

      <Dialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{selected?.label ?? 'Group'}</DialogTitle>
            <DialogDescription>
              {selected
                ? `${formatCurrency(selected.total_value)} (${selected.percentage.toFixed(
                    1,
                  )}% of portfolio)`
                : ''}
            </DialogDescription>
          </DialogHeader>
          {selected && (
            <div className="max-h-[60vh] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-muted-foreground">
                  <tr className="border-b border-border/40">
                    <th className="py-2 pr-2 text-left font-medium">Symbol</th>
                    <th className="py-2 pr-2 text-right font-medium">Value</th>
                    <th className="py-2 text-right font-medium">% of portfolio</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.holdings.map((h) => (
                    <tr key={h.symbol} className="border-b border-border/20">
                      <td className="py-2 pr-2 font-medium text-foreground">{h.symbol}</td>
                      <td className="py-2 pr-2 text-right text-muted-foreground">
                        {formatCurrency(h.value)}
                      </td>
                      <td className="py-2 text-right text-muted-foreground">
                        {h.percentage.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
