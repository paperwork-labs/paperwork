import * as React from 'react';
import { Page, PageHeader } from '@/components/ui/Page';
import { TabbedPageShell } from '@/components/layout/TabbedPageShell';
import SentimentBanner from '@/components/regime/SentimentBanner';
import { SyncStatusStrip } from '@/components/portfolio/SyncStatusStrip';

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
  return (
    <Page>
      <div className="flex flex-col gap-4">
        <PageHeader
          title="Portfolio"
          subtitle="Overview, allocation, performance history, and risk metrics"
          rightContent={<SyncStatusStrip />}
        />

        <SentimentBanner />

        <TabbedPageShell tabs={PORTFOLIO_TABS} defaultTab="overview" />
      </div>
    </Page>
  );
}
