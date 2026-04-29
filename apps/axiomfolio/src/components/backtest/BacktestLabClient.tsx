"use client";

import * as React from "react";

import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";

const WalkForwardClient = React.lazy(() => import("@/components/backtest/WalkForwardClient"));
const MonteCarloClient = React.lazy(() => import("@/components/backtest/MonteCarloClient"));

const BACKTEST_TABS = [
  { id: "walk-forward" as const, label: "Walk-forward", Content: WalkForwardClient },
  { id: "monte-carlo" as const, label: "Monte Carlo", Content: MonteCarloClient },
];

export default function BacktestLabClient() {
  return (
    <div className="w-full">
      <TabbedPageShell tabs={BACKTEST_TABS} defaultTab="walk-forward" />
    </div>
  );
}
