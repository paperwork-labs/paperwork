// Ladle configuration for the AxiomFolio Vite app — this app doubles as the
// monorepo's design-system / story canvas (the existing brand, motion, token,
// chart and primitives stories all live in src/stories or alongside their
// components). Components shipped from packages/* with co-located *.stories.tsx
// files are hoisted in via the second glob so we don't duplicate Storybook
// installs across the workspace (see docs/brand/ANIMATION.md § Storybook
// follow-up — agreed approach is "extend the existing story system, don't
// stand up a second one").
//
// Reference: https://ladle.dev/docs/config

/** @type {import("@ladle/react/lib/shared/types").Config} */
export default {
  stories: [
    "src/**/*.stories.{js,jsx,ts,tsx,mdx}",
    "../../packages/**/src/**/*.stories.{js,jsx,ts,tsx,mdx}",
  ],
};
