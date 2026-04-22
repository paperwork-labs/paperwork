import * as React from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { Page, PageHeader } from '@/components/ui/Page';
import { Button } from '@/components/ui/button';
import { TabbedPageShell } from '@/components/layout/TabbedPageShell';
import { usePortfolioSync } from '@/hooks/usePortfolio';

const OverviewTab = React.lazy(() => import('./tabs/OverviewTab'));
const AllocationTab = React.lazy(() => import('./tabs/AllocationTab'));
const PerformanceTab = React.lazy(() => import('./tabs/PerformanceTab'));
const RiskTab = React.lazy(() => import('./tabs/RiskTab'));

const PORTFOLIO_TABS = [
  { id: 'overview' as const, label: 'Overview', Content: OverviewTab },
  { id: 'allocation' as const, label: 'Allocation', Content: AllocationTab },
  { id: 'performance' as const, label: 'Performance', Content: PerformanceTab },
  { id: 'risk' as const, label: 'Risk', Content: RiskTab },
];

export type PortfolioShellTabId = (typeof PORTFOLIO_TABS)[number]['id'];

export default function PortfolioTabShell() {
  const syncMutation = usePortfolioSync();

  return (
    <Page>
      <div className="flex flex-col gap-4">
        <PageHeader
          title="Portfolio"
          subtitle="Overview, allocation, performance history, and risk metrics"
          rightContent={
            <Button
              size="sm"
              variant="outline"
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="gap-2"
            >
              {syncMutation.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <RefreshCw className="size-4" aria-hidden />
              )}
              Sync
            </Button>
          }
        />

        <TabbedPageShell tabs={PORTFOLIO_TABS} defaultTab="overview" />
      </div>
    </Page>
  );
}
