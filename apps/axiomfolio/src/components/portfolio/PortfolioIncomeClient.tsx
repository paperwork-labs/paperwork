"use client";

/**
 * `/portfolio/income` — Snowball-style dividend income calendar page.
 *
 * Thin shell: layout chrome + page header. All data fetching, mode
 * toggles, and rendering live in `<IncomeCalendar />`.
 */
import * as React from "react";

import { IncomeCalendar } from "@/components/portfolio/IncomeCalendar";
import { Page, PageHeader } from "@/components/ui/Page";

const PortfolioIncomeClient: React.FC = () => {
  return (
    <Page>
      <PageHeader
        title="Income"
        subtitle="Dividend income, by pay date — historical or projected for the next 12 months."
      />
      <IncomeCalendar />
    </Page>
  );
};

export default PortfolioIncomeClient;
