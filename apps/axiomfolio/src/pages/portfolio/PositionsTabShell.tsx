import * as React from 'react';
import { useSearchParams } from 'react-router-dom';

import { Page, PageHeader } from '@/components/ui/Page';
import { TabbedPageShell } from '@/components/layout/TabbedPageShell';

// Lazy the heavy table pages — each is 700-1800 LOC and owns its own data
// fetching. Keeping them lazy means clicking a tab is the trigger for the
// fetch, not mounting the shell.
const HoldingsTab = React.lazy(() => import('./PortfolioHoldings'));
const OptionsTab = React.lazy(() => import('./PortfolioOptions'));
const CategoriesTab = React.lazy(() => import('./PortfolioCategories'));

const POSITIONS_TABS = [
  { id: 'holdings' as const, label: 'Holdings', Content: HoldingsTab },
  { id: 'options' as const, label: 'Options', Content: OptionsTab },
  { id: 'categories' as const, label: 'Categories', Content: CategoriesTab },
];

export type PositionsShellTabId = (typeof POSITIONS_TABS)[number]['id'];

// Transitional aliases — preserve old bookmarks/deep-links that predate the
// Wave-B IA correction. `?tab=lots` used to mount the full Tax Center under a
// sub-tab; that view has moved to `/portfolio/tax` (sidebar) and the slot it
// used to occupy is now Categories. Rewrite in place so no one lands on a
// 404-shaped empty tab.
const TAB_ALIASES: Record<string, PositionsShellTabId> = {
  lots: 'categories',
};

/**
 * `/portfolio/positions` — the consolidated Positions hub.
 *
 * Collapses the former standalone sidebar entries for Holdings, Options,
 * and Categories into a single page with a tab strip. The previous "Lots"
 * tab (which hosted the full Tax Center) was promoted back to a first-class
 * destination at `/portfolio/tax`; Categories takes the freed slot because
 * "which bucket does this position belong to?" is the natural third axis
 * alongside Holdings / Options.
 */
export default function PositionsTabShell() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get('tab') ?? '';
  const aliasTarget = TAB_ALIASES[rawTab];

  React.useEffect(() => {
    if (!aliasTarget) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', aliasTarget);
        return next;
      },
      { replace: true },
    );
  }, [aliasTarget, setSearchParams]);

  return (
    <Page>
      <div className="flex flex-col gap-4">
        <PageHeader
          title="Positions"
          subtitle="Holdings, options, and category buckets — all the instruments you currently own."
        />
        <TabbedPageShell tabs={POSITIONS_TABS} defaultTab="holdings" />
      </div>
    </Page>
  );
}
