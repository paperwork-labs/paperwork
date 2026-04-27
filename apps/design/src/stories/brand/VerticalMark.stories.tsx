import type { Meta, StoryObj } from "@storybook/react";

import { VerticalMark } from "@paperwork-labs/ui/brand";

const meta = {
  title: "Brand/VerticalMark (P2)",
  component: VerticalMark,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
  },
} satisfies Meta<typeof VerticalMark>;

export default meta;
type Story = StoryObj<typeof meta>;

export const AppIcon: Story = {
  name: "App icon size",
  render: (args) => (
    <div className="text-slate-900" style={{ ["--pwl-clip-accent" as string]: "#f59e0b" }}>
      <VerticalMark {...args} className="h-8 w-8" />
    </div>
  ),
  parameters: {
    chromatic: { delay: 100 },
  },
};

export const Large: Story = {
  render: (args) => (
    <div className="text-slate-900" style={{ ["--pwl-clip-accent" as string]: "#f59e0b" }}>
      <VerticalMark {...args} className="h-32 w-32" />
    </div>
  ),
};
