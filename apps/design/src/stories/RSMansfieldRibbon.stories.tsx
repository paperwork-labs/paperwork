import { RSMansfieldRibbon } from '@axiomfolio/components/charts/RSMansfieldRibbon';
import type { Meta, StoryObj } from "@storybook/react";

const meta: Meta = {
  title: 'Charts / RSMansfieldRibbon',
};
export default meta;

type Story = StoryObj;

function mkPoints(n: number, sign: 1 | -1, start = '2024-01-02') {
  const out: { date: string; value: number }[] = [];
  for (let i = 0; i < n; i++) {
    const d = new Date(`${start}T00:00:00Z`);
    d.setUTCDate(d.getUTCDate() + i);
    out.push({
      date: d.toISOString().slice(0, 10),
      value: sign * (2 + Math.sin(i / 8) * 3),
    });
  }
  return out;
}

export const Loading: Story = {
  render: () => (
  <div className="max-w-3xl bg-background p-4">
    <RSMansfieldRibbon isPending isError={false} error={null} onRetry={() => {}} points={[]} />
  </div>
),
};

/** Successful fetch with no finite points — muted unavailable bar. */
export const Empty: Story = {
  render: () => (
  <div className="max-w-3xl bg-background p-4">
    <RSMansfieldRibbon isPending={false} isError={false} error={null} onRetry={() => {}} points={[]} />
  </div>
),
};

export const Outperforming: Story = {
  render: () => (
  <div className="max-w-3xl bg-background p-4">
    <RSMansfieldRibbon
      isPending={false}
      isError={false}
      error={null}
      onRetry={() => {}}
      points={mkPoints(120, 1)}
      benchmark="SPY"
    />
  </div>
),
};

export const Underperforming: Story = {
  render: () => (
  <div className="max-w-3xl bg-background p-4">
    <RSMansfieldRibbon
      isPending={false}
      isError={false}
      error={null}
      onRetry={() => {}}
      points={mkPoints(120, -1)}
      benchmark="SPY"
    />
  </div>
),
};

/** Named Errored (not Error) to avoid shadowing the global Error constructor (D41). */
export const Errored: Story = {
  render: () => (
  <div className="max-w-3xl bg-background p-4">
    <RSMansfieldRibbon
      isPending={false}
      isError
      error={new Error('Request failed')}
      onRetry={() => {}}
      points={[]}
    />
  </div>
),
};
