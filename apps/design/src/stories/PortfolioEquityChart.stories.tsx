import * as React from "react";

import { PortfolioEquityChart } from "@axiomfolio/components/charts/PortfolioEquityChart";
import type { Meta, StoryObj } from "@storybook/react";

const meta: Meta = {
  title: "Charts / PortfolioEquityChart",
};
export default meta;

type Story = StoryObj;

const sampleData = [
  { date: "2024-01-01", total_value: 100_000 },
  { date: "2024-02-01", total_value: 108_000 },
  { date: "2024-03-01", total_value: 102_000 },
];

const samplePoints = [
  { time: 1_704_067_200 as import("lightweight-charts").UTCTimestamp, equity: 100_000, benchmark: 100_000 },
  { time: 1_706_745_600 as import("lightweight-charts").UTCTimestamp, equity: 108_000, benchmark: 104_000 },
  { time: 1_709_164_800 as import("lightweight-charts").UTCTimestamp, equity: 102_000, benchmark: 103_000 },
];

export const Loading: Story = {
  render: () => (
  <div className="max-w-3xl p-4">
    <PortfolioEquityChart
      isPending
      isError={false}
      error={null}
      onRetry={() => {}}
      data={undefined}
      chartPoints={[]}
      hasBenchmark={false}
      valueMode="usd"
      onValueModeChange={() => {}}
    />
  </div>
),
};

export const Errored: Story = {
  render: () => (
  <div className="max-w-3xl p-4">
    <PortfolioEquityChart
      isPending={false}
      isError
      error={new globalThis.Error("network")}
      onRetry={() => {}}
      data={undefined}
      chartPoints={[]}
      hasBenchmark={false}
      valueMode="usd"
      onValueModeChange={() => {}}
    />
  </div>
),
};

export const Empty: Story = {
  render: () => (
  <div className="max-w-3xl p-4">
    <PortfolioEquityChart
      isPending={false}
      isError={false}
      error={null}
      onRetry={() => {}}
      data={[]}
      chartPoints={[]}
      hasBenchmark={false}
      valueMode="usd"
      onValueModeChange={() => {}}
    />
  </div>
),
};

export const WithData: Story = {
  render: () => {
  const [mode, setMode] = React.useState<"usd" | "pct">("usd");
  return (
    <div className="max-w-3xl p-4">
      <PortfolioEquityChart
        isPending={false}
        isError={false}
        error={null}
        onRetry={() => {}}
        data={sampleData}
        chartPoints={samplePoints}
        hasBenchmark
        valueMode={mode}
        onValueModeChange={setMode}
      />
    </div>
  );
},
};
