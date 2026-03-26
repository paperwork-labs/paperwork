import React from 'react';
import { Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface Props {
  marketOnlyMode: boolean;
  portfolioEnabled: boolean;
  strategyEnabled: boolean;
  toggling: boolean;
  onToggleMarketOnly: () => void;
  onTogglePortfolio: () => void;
  onToggleStrategy: () => void;
}

function onBadgeClass(on: boolean): string {
  return on
    ? 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]'
    : 'border-transparent bg-muted text-muted-foreground';
}

const AdminReleaseControls: React.FC<Props> = ({
  marketOnlyMode,
  portfolioEnabled,
  strategyEnabled,
  toggling,
  onToggleMarketOnly,
  onTogglePortfolio,
  onToggleStrategy,
}) => {
  return (
    <div className="mb-3 rounded-lg border border-border bg-muted/50 p-3">
      <p className="mb-1 text-sm font-semibold text-foreground">Release Controls</p>
      <p className="mb-3 text-xs text-muted-foreground">
        Keep market-only enabled while building. Disable market-only and enable sections when ready.
      </p>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm">Market-only mode</p>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={cn('font-medium', onBadgeClass(marketOnlyMode))}>
            {marketOnlyMode ? 'ON' : 'OFF'}
          </Badge>
          <Button
            size="xs"
            variant="outline"
            disabled={toggling}
            onClick={onToggleMarketOnly}
            className="inline-flex gap-1.5"
          >
            {toggling ? <Loader2 className="size-3 shrink-0 animate-spin" aria-hidden /> : null}
            {marketOnlyMode ? 'Disable' : 'Enable'}
          </Button>
        </div>
      </div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm">Portfolio section</p>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={cn('font-medium', onBadgeClass(portfolioEnabled))}>
            {portfolioEnabled ? 'ENABLED' : 'DISABLED'}
          </Badge>
          <Button
            size="xs"
            variant="outline"
            disabled={toggling}
            onClick={onTogglePortfolio}
            className="inline-flex gap-1.5"
          >
            {toggling ? <Loader2 className="size-3 shrink-0 animate-spin" aria-hidden /> : null}
            {portfolioEnabled ? 'Disable' : 'Enable'}
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm">Strategy section</p>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={cn('font-medium', onBadgeClass(strategyEnabled))}>
            {strategyEnabled ? 'ENABLED' : 'DISABLED'}
          </Badge>
          <Button
            size="xs"
            variant="outline"
            disabled={toggling}
            onClick={onToggleStrategy}
            className="inline-flex gap-1.5"
          >
            {toggling ? <Loader2 className="size-3 shrink-0 animate-spin" aria-hidden /> : null}
            {strategyEnabled ? 'Disable' : 'Enable'}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default AdminReleaseControls;
