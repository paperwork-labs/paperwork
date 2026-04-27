import type { Meta, StoryObj } from "@storybook/react";

import { ClipMark } from "./ClipMark";

const meta = {
  title: "Brand/ClipMark (P1)",
  component: ClipMark,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
  },
} satisfies Meta<typeof ClipMark>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: (args) => (
    <div className="text-slate-900" style={{ ["--pwl-clip-accent" as string]: "#f59e0b" }}>
      <ClipMark {...args} className="h-32 w-32" />
    </div>
  ),
};

export const OnDark: Story = {
  name: "On dark surface",
  render: (args) => (
    <div
      className="rounded-md bg-slate-900 p-8 text-slate-50"
      style={{ ["--pwl-clip-accent" as string]: "#fbbf24" }}
    >
      <ClipMark {...args} className="h-24 w-24" />
    </div>
  ),
};
