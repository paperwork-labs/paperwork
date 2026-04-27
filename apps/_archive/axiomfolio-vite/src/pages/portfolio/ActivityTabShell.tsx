import * as React from 'react';

import { Page, PageHeader } from '@/components/ui/Page';
import { TabbedPageShell } from '@/components/layout/TabbedPageShell';

const OrdersTab = React.lazy(() => import('./PortfolioOrders'));
const TransactionsTab = React.lazy(() => import('./PortfolioTransactions'));
const IncomeTab = React.lazy(() => import('../PortfolioIncome'));

const ACTIVITY_TABS = [
  { id: 'orders' as const, label: 'Orders', Content: OrdersTab },
  { id: 'transactions' as const, label: 'Transactions', Content: TransactionsTab },
  { id: 'income' as const, label: 'Income', Content: IncomeTab },
];

export type ActivityShellTabId = (typeof ACTIVITY_TABS)[number]['id'];

/**
 * `/portfolio/activity` — the consolidated Activity hub.
 *
 * Collapses Orders, Transactions (trades), and Dividend Income into a
 * single page with a tab strip. Realized P&L lives inside the Tax Center
 * (Positions > Lots) where the lot-level detail is already surfaced,
 * rather than duplicating the view here.
 */
export default function ActivityTabShell() {
  return (
    <Page>
      <div className="flex flex-col gap-4">
        <PageHeader
          title="Activity"
          subtitle="Orders, transactions, and dividend income — everything that has moved in or out of your accounts."
        />
        <TabbedPageShell tabs={ACTIVITY_TABS} defaultTab="orders" />
      </div>
    </Page>
  );
}
