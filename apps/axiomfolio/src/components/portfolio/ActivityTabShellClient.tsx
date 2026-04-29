"use client";

import * as React from "react";

import { Page, PageHeader, TabbedPageShell } from "@paperwork-labs/ui";

const OrdersTab = React.lazy(() => import("@/components/portfolio/PortfolioOrdersClient"));
const TransactionsTab = React.lazy(() => import("@/components/portfolio/PortfolioTransactionsClient"));
const IncomeTab = React.lazy(() => import("@/components/portfolio/PortfolioIncomeClient"));

const ACTIVITY_TABS = [
  { id: "orders" as const, label: "Orders", Content: OrdersTab },
  { id: "transactions" as const, label: "Transactions", Content: TransactionsTab },
  { id: "income" as const, label: "Income", Content: IncomeTab },
];

export type ActivityShellTabId = (typeof ACTIVITY_TABS)[number]["id"];

export default function ActivityTabShellClient() {
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
