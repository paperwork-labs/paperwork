import type { Meta, StoryObj } from "@storybook/react";

import { Input, Label } from "@paperwork-labs/ui";

const meta = {
  title: "UI/Input",
  component: Input,
  tags: ["autodocs"],
} satisfies Meta<typeof Input>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    placeholder: "Email",
    type: "email",
  },
};

export const WithLabel: Story = {
  name: "With label",
  render: () => (
    <div className="grid w-full max-w-sm gap-2">
      <Label htmlFor="demo-email">Email</Label>
      <Input id="demo-email" type="email" placeholder="you@company.com" />
    </div>
  ),
};

export const Disabled: Story = {
  args: {
    disabled: true,
    placeholder: "Disabled",
  },
};
