import type { CSSProperties } from "react";
import type { Story } from "@ladle/react";
import { ClippedWordmark } from "./ClippedWordmark";

// NOTE: this monorepo uses Ladle (`@ladle/react`) as the story system rather
// than Storybook proper — the existing brand / token / motion stories live
// under apps/axiomfolio/src/stories and are picked up by `pnpm --filter
// @paperwork-labs/axiomfolio ladle:build`. This file follows the same CSF
// pattern as those stories and is hoisted into Ladle's glob via
// apps/axiomfolio/.ladle/config.mjs.
//
// The component itself is currently a placeholder stub — see the TODO in
// ClippedWordmark.tsx. Once `brand/p5-clipped-wordmark-svg` lands the stub
// is replaced by the real framer-motion + SVG composition; these stories
// keep working without changes.

export default {
  title: "Brand / Paperwork Labs / Clipped Wordmark (P5)",
  meta: {
    description: [
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
};

interface ClippedWordmarkArgs {
  animated: boolean;
}

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

export const Animated: Story<ClippedWordmarkArgs> = ({ animated }) => (
  <div style={LightSurface}>
    <ClippedWordmark animated={animated} />
  </div>
);
Animated.args = { animated: true };
Animated.argTypes = {
  animated: { control: { type: "boolean" }, defaultValue: true },
};
Animated.storyName = "Animated (entrance plays once)";
Animated.meta = {
  description: [
    "Plays the clip-on entrance once, then settles into the static end state.",
    "Production behavior is once-per-session via sessionStorage; the Ladle",
    "canvas re-runs on every reload. Toggle the `animated` arg or refresh the",
    "page to re-trigger the entrance.",
  ].join(" "),
};

export const Static: Story = () => (
  <div style={LightSurface}>
    <ClippedWordmark animated={false} />
  </div>
);
Static.storyName = "Static (end state, no animation)";
Static.meta = {
  description: [
    "Static end-state — no entrance animation. Used in footer attribution,",
    "OG cards, business cards, investor decks, and email signature.",
  ].join(" "),
};

export const ReducedMotion: Story = () => (
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
      Toggle <strong>Reduce Motion</strong> in your OS (macOS:
      System Settings → Accessibility → Display) and reload to verify the
      entrance is suppressed and the component renders the static end state
      on frame 1. Reduced-motion handling is mandatory per
      <code> docs/brand/ANIMATION.md § Reduced-motion handling</code>.
    </p>
    <ClippedWordmark animated />
  </div>
);
ReducedMotion.storyName = "Reduced Motion (skips entrance)";
ReducedMotion.meta = {
  description: [
    "When the user has `prefers-reduced-motion: reduce`, the component skips",
    "the entrance animation entirely and renders the static end state on",
    "frame 1 — no fade-in either. Accessibility users get the brand in its",
    "final form on first paint.",
  ].join(" "),
  a11y: {
    rules: [{ id: "color-contrast", reviewOnFail: true }],
  },
};

export const DarkSurface: Story = () => (
  <div style={DarkSurfaceStyle}>
    <ClippedWordmark animated={false} surface="dark" />
  </div>
);
DarkSurface.storyName = "Dark surface (slate-night background)";
DarkSurface.meta = {
  description: [
    "On dark surfaces (#0F172A or darker), wire + wordmark switch to",
    "near-white #F8FAFC and the accent shifts amber-500 → amber-300",
    "(#FBBF24) per the dark-surface variant rule in",
    "`.cursor/rules/brand.mdc § Visual grammar`.",
  ].join(" "),
};

export const HoverWiggle: Story = () => (
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
    <ClippedWordmark animated />
  </div>
);
HoverWiggle.storyName = "Hover wiggle (header behavior)";
HoverWiggle.meta = {
  description: [
    "Header-only hover micro-interaction. Skipped on touch devices (no",
    "hover) and when prefers-reduced-motion is set. Demoed here on a static",
    "Ladle canvas; in production the wiggle is wired via framer-motion's",
    "`whileHover` on the clip span.",
  ].join(" "),
};
