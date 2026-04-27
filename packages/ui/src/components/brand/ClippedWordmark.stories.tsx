import type { Meta, StoryObj } from "@storybook/react";
import { userEvent, within } from "@storybook/test";

import { ClippedWordmark } from "./ClippedWordmark";

const meta = {
  title: "Brand/ClippedWordmark (P5)",
  component: ClippedWordmark,
  tags: ["autodocs"],
  args: {
    animated: false,
    surface: "light" as const,
  },
} satisfies Meta<typeof ClippedWordmark>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    animated: false,
    surface: "light",
  },
};

export const Animated: Story = {
  args: {
    animated: true,
    surface: "light",
  },
  parameters: {
    chromatic: { delay: 1200 },
  },
};

export const Static: Story = {
  args: {
    animated: false,
    surface: "light",
  },
};

export const ReducedMotion: Story = {
  name: "Reduced motion",
  args: {
    animated: true,
    surface: "light",
  },
  decorators: [
    (StoryFn) => {
      const original = window.matchMedia.bind(window);
      window.matchMedia = function matchMedia(query: string) {
        if (String(query).includes("prefers-reduced-motion")) {
          return {
            matches: true,
            media: query,
            addEventListener: () => {},
            removeEventListener: () => {},
            addListener: () => {},
            removeListener: () => {},
            dispatchEvent: () => false,
            onchange: null,
          } as MediaQueryList;
        }
        return original(query);
      };
      return <StoryFn />;
    },
  ],
  parameters: {
    chromatic: { disableSnapshot: true },
  },
};

export const DarkSurface: Story = {
  args: {
    animated: false,
    surface: "dark",
  },
  parameters: {
    backgrounds: { default: "slate-night" },
    chromatic: { delay: 200 },
  },
  decorators: [
    (StoryFn) => (
      <div className="rounded-lg p-6" style={{ background: "#0f172a" }}>
        <StoryFn />
      </div>
    ),
  ],
};

export const HoverWiggle: Story = {
  args: {
    animated: true,
    surface: "light",
  },
  play: async ({ canvasElement }) => {
    const root = within(canvasElement);
    const mark = root.getByLabelText("Paperwork Labs");
    await userEvent.hover(mark);
  },
  parameters: {
    chromatic: { delay: 500 },
  },
};
