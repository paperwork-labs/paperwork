import type { Meta, StoryObj } from "@storybook/react";

import { Wordmark } from "@paperwork-labs/ui/brand";

const meta = {
  title: "Brand/Wordmark",
  component: Wordmark,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
  },
} satisfies Meta<typeof Wordmark>;

export default meta;
type Story = StoryObj<typeof meta>;

export const InterTight600: Story = {
  name: "Inter Tight 600",
  render: (args) => (
    <div className="max-w-3xl text-slate-900">
      <Wordmark {...args} className="h-12 w-auto" />
    </div>
  ),
};

export const OnDark: Story = {
  name: "On dark",
  render: (args) => (
    <div className="max-w-3xl rounded-md bg-slate-900 p-6 text-slate-50">
      <Wordmark {...args} className="h-10 w-auto" />
    </div>
  ),
};
