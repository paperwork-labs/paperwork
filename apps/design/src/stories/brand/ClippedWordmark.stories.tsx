import type { CSSProperties } from "react";

import type { Meta, StoryObj } from "@storybook/react";

import { ClippedWordmark } from "@paperwork-labs/ui/brand";

// The component itself is currently a placeholder stub — see the TODO in
// ClippedWordmark.tsx. Once `brand/p5-clipped-wordmark-svg` lands the stub is
// replaced by the real framer-motion + SVG composition; these stories keep
// working without changes because the props surface stays the same.

const LightSurface: CSSProperties = {
  background: "#F8FAFC",
  padding: "64px 48px",
  minWidth: 520,
};

const DarkSurfaceStyle: CSSProperties = {
  background: "#0F172A",
  padding: "64px 48px",
  minWidth: 520,
};

const meta: Meta<typeof ClippedWordmark> = {
  title: "Brand/Paperwork Labs/Clipped Wordmark (P5)",
  component: ClippedWordmark,
  parameters: {
    layout: "fullscreen",
    backgrounds: { default: "light" },
    docs: {
      description: {
        component: [
          "The canonical 'clipped wordmark' composition (P5) — the paperclip mark",
          "visually clipping 'Paperwork Labs' from the top-left, the way a real",
          "paperclip pins a sheet of paper.",
          "",
          "Spec: docs/brand/PROMPTS.md § P5 and docs/brand/ANIMATION.md for the",
          "full motion + reduced-motion + dark-surface specification. This is the",
          "most distinctive surface treatment of the parent brand; use only on",
          "paperworklabs.com nav, app load splash, Studio admin sidebar entrance,",
          "founder mode hero, and similar surfaces. Never use as a favicon — clip",
          "detail dies under 24 px (use P2 vertical mark instead).",
        ].join("\n"),
      },
    },
  },
  argTypes: {
    animated: { control: { type: "boolean" } },
    surface: {
      control: { type: "inline-radio" },
      options: ["light", "dark"],
    },
  },
};

export default meta;

type Story = StoryObj<typeof ClippedWordmark>;

export const Animated: Story = {
  name: "Animated (entrance animation)",
  args: { animated: true },
  parameters: {
    docs: {
      description: {
        story: [
          "Plays the clip-on entrance animation, then settles into the static end state.",
          "In this story, the entrance runs whenever `animated` is enabled and the",
          "component is re-rendered from a fresh mount. Toggle the `animated` arg or",
          "refresh the page to re-trigger the entrance. Production surfaces gate this",
          "to once-per-session via sessionStorage at the consumer (e.g. Studio header);",
          "see docs/brand/ANIMATION.md § Triggering for the canonical wiring.",
        ].join(" "),
      },
    },
  },
  render: (args) => (
    <div style={LightSurface}>
      <ClippedWordmark {...args} />
    </div>
  ),
};

export const Static: Story = {
  name: "Static (end state, no animation)",
  args: { animated: false },
  parameters: {
    docs: {
      description: {
        story: [
          "Static end-state — no entrance animation. Used in footer attribution,",
          "OG cards, business cards, investor decks, and email signature.",
        ].join(" "),
      },
    },
  },
  render: (args) => (
    <div style={LightSurface}>
      <ClippedWordmark {...args} />
    </div>
  ),
};

export const ReducedMotion: Story = {
  name: "Reduced Motion (skips entrance)",
  args: { animated: true },
  parameters: {
    docs: {
      description: {
        story: [
          "When the user has `prefers-reduced-motion: reduce`, the component skips",
          "the entrance animation entirely and renders the static end state on",
          "frame 1 — no fade-in either. Accessibility users get the brand in its",
          "final form on first paint.",
        ].join(" "),
      },
    },
    a11y: {
      config: {
        rules: [{ id: "color-contrast", reviewOnFail: true }],
      },
    },
  },
  render: (args) => (
    <div style={LightSurface}>
      <p
        style={{
          marginBottom: 24,
          maxWidth: 480,
          color: "#475569",
          fontFamily: "Inter, system-ui, sans-serif",
          fontSize: 13,
          lineHeight: 1.5,
        }}
      >
        Toggle <strong>Reduce Motion</strong> in your OS (macOS: System Settings
        → Accessibility → Display) and reload to verify the entrance is
        suppressed and the component renders the static end state on frame 1.
        Reduced-motion handling is mandatory per
        <code> docs/brand/ANIMATION.md § Reduced-motion handling</code>.
      </p>
      <ClippedWordmark {...args} />
    </div>
  ),
};

export const DarkSurface: Story = {
  name: "Dark surface (slate-night background)",
  args: { animated: false, surface: "dark" },
  parameters: {
    backgrounds: { default: "slate-night" },
    docs: {
      description: {
        story: [
          "On dark surfaces (#0F172A or darker), wire + wordmark switch to",
          "near-white #F8FAFC and the accent shifts amber-500 → amber-300",
          "(#FBBF24) per the dark-surface variant rule in",
          "`.cursor/rules/brand.mdc § Visual grammar`.",
        ].join(" "),
      },
    },
  },
  render: (args) => (
    <div style={DarkSurfaceStyle}>
      <ClippedWordmark {...args} />
    </div>
  ),
};

export const HoverWiggle: Story = {
  name: "Hover wiggle (header behavior)",
  args: { animated: true },
  parameters: {
    docs: {
      description: {
        story: [
          "Header-only hover micro-interaction. Skipped on touch devices (no",
          "hover) and when prefers-reduced-motion is set. Demoed here on a static",
          "Storybook canvas; in production the wiggle is wired via framer-motion's",
          "`whileHover` on the clip span.",
        ].join(" "),
      },
    },
  },
  render: (args) => (
    <div style={LightSurface}>
      <p
        style={{
          marginBottom: 24,
          maxWidth: 480,
          color: "#475569",
          fontFamily: "Inter, system-ui, sans-serif",
          fontSize: 13,
          lineHeight: 1.5,
        }}
      >
        Hover the clip — subtle wiggle (-15° → -13° → -17° → -15° over 320ms,
        easeInOut). Header-only behavior in production; suppressed on touch
        devices and when reduced motion is set.
      </p>
      <ClippedWordmark {...args} />
    </div>
  ),
};
