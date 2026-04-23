import * as React from 'react';

import { Page, PageHeader } from '@/components/ui/Page';
import { TabbedPageShell } from '@/components/layout/TabbedPageShell';

// Lazy the heavy table pages — each is 700-1800 LOC and owns its own data
// fetching. Keeping them lazy means clicking a tab is the trigger for the
// fetch, not mounting the shell.
const HoldingsTab = React.lazy(() => import('./PortfolioHoldings'));
const OptionsTab = React.lazy(() => import('./PortfolioOptions'));
const LotsTab = React.lazy(() => import('./PortfolioTaxCenter'));

const POSITIONS_TABS = [
  { id: 'holdings' as const, label: 'Holdings', Content: HoldingsTab },
  { id: 'options' as const, label: 'Options', Content: OptionsTab },
  { id: 'lots' as const, label: 'Lots', Content: LotsTab },
];

export type PositionsShellTabId = (typeof POSITIONS_TABS)[number]['id'];

/**
 * `/portfolio/positions` — the consolidated Positions hub.
 *
 * Collapses the former standalone sidebar entries for Holdings, Options,
 * and Tax Lots into a single page with a tab strip. Runners (positions
 * past initial risk) will slot in here once the backing metric ships;
 * until then the three-tab shell keeps the surface honest.
 */
export default function PositionsTabShell() {
  return (
    <Page>
      <div className="flex flex-col gap-4">
        <PageHeader
          title="Positions"
          subtitle="Holdings, options, and tax lots — all the instruments you currently own."
        />
        <TabbedPageShell tabs={POSITIONS_TABS} defaultTab="holdings" />
      </div>
    </Page>
  );
}
