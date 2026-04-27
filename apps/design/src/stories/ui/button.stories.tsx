import type { Meta, StoryObj } from "@storybook/react";
import { Mail } from "lucide-react";

import { Button } from "@paperwork-labs/ui";

const meta = {
  title: "UI/Button",
  component: Button,
  tags: ["autodocs"],
  argTypes: {
    variant: {
      control: "select",
      options: ["default", "destructive", "outline", "secondary", "ghost", "link"],
    },
    size: { control: "select", options: ["default", "sm", "lg", "icon"] },
  },
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    children: "Button",
  },
};

export const Destructive: Story = {
  args: {
    children: "Delete",
    variant: "destructive",
  },
};

export const Outline: Story = {
  args: {
    children: "Outline",
    variant: "outline",
  },
};

export const WithIcon: Story = {
  args: {
    children: (
      <>
        <Mail />
        Login with email
      </>
    ),
  },
};

export const AsChild: Story = {
  name: "As link (asChild)",
  render: () => (
    <Button asChild>
      <a href="https://paperworklabs.com">Visit</a>
    </Button>
  ),
};
