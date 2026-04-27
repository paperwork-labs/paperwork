import * as React from "react";

import { DrawdownUnderwater } from "@axiomfolio/components/charts/DrawdownUnderwater";
import type { Meta, StoryObj } from "@storybook/react";

const meta: Meta = {
  title: "Charts / DrawdownUnderwater",
};
export default meta;

type Story = StoryObj;

const sampleData = [
  { date: "2024-01-01", total_value: 100_000 },
  { date: "2024-02-01", total_value: 110_000 },
  { date: "2024-03-01", total_value: 95_000 },
  { date: "2024-04-01", total_value: 120_000 },
];

export const Loading: Story = {
  render: () => (
  <div className="max-w-3xl p-4">
    <DrawdownUnderwater
      isPending
      isError={false}
      error={null}
      onRetry={() => {}}
      data={undefined}
    />
  </div>
),
};

export const Errored: Story = {
  render: () => (
  <div className="max-w-3xl p-4">
    <DrawdownUnderwater
      isPending={false}
      isError
      error={new globalThis.Error("network")}
      onRetry={() => {}}
      data={undefined}
    />
  </div>
),
};

export const Empty: Story = {
  render: () => (
  <div className="max-w-3xl p-4">
    <DrawdownUnderwater
      isPending={false}
      isError={false}
      error={null}
      onRetry={() => {}}
      data={[]}
    />
  </div>
),
};

export const WithData: Story = {
  render: () => (
  <div className="max-w-3xl p-4">
    <DrawdownUnderwater
      isPending={false}
      isError={false}
      error={null}
      onRetry={() => {}}
      data={sampleData}
    />
  </div>
),
};
