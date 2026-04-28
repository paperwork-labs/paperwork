import type { StorybookConfig } from "@storybook/react-vite";
import tailwindcss from "@tailwindcss/vite";

/**
 * Design canvas (design.paperworklabs.com) is self-contained: stories live under
 * `apps/design/src/**` and resolve only this app plus workspace packages (e.g.
 * `@paperwork-labs/ui`). We previously aliased `@axiomfolio` and `@` into
 * `apps/axiomfolio/src` for migrated Ladle stories; that caused rolldown
 * (Vite 8) to fail extension resolution on those cross-root imports. Those
 * aliases are intentionally removed — keep stories inside this package.
 */
const config: StorybookConfig = {
  stories: [
    "../src/**/*.mdx",
    "../src/**/*.stories.@(js|jsx|mjs|ts|tsx)",
    "../../../packages/**/src/**/*.stories.@(js|jsx|mjs|ts|tsx)",
  ],
  addons: [
    "@storybook/addon-a11y",
    "@storybook/addon-docs",
    "@storybook/addon-themes",
  ],
  framework: { name: "@storybook/react-vite", options: {} },
  typescript: {
    check: false,
    // `react-docgen` reads JSDoc + prop types without requiring every file to
    // sit in the active tsconfig project (helpful when package stories import
    // from their own package trees).
    reactDocgen: "react-docgen",
  },
  viteFinal: async (vite) => {
    vite.plugins = vite.plugins ?? [];
    vite.plugins.push(tailwindcss());
    return vite;
  },
};

export default config;
