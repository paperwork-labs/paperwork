import { fileURLToPath } from "node:url";

import type { StorybookConfig } from "@storybook/react-vite";

/** Monorepo root (…/apps/design/.storybook → ../../../). */
const repoRoot = fileURLToPath(new URL("../../..", import.meta.url));

const config: StorybookConfig = {
  stories: [
    "../src/**/*.stories.@(ts|tsx|mdx)",
    "../src/**/*.mdx",
    "../../../packages/**/src/**/*.stories.@(ts|tsx|mdx)",
  ],
  addons: [
    "@storybook/addon-essentials",
    "@storybook/addon-a11y",
    "@storybook/addon-interactions",
    "@storybook/addon-themes",
  ],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  async viteFinal(vite) {
    const { mergeConfig } = await import("vite");
    const tailwind = (await import("@tailwindcss/vite")).default;
    const storybookReact = fileURLToPath(
      new URL("../node_modules/@storybook/react", import.meta.url),
    );
    const storybookTest = fileURLToPath(
      new URL("../node_modules/@storybook/test", import.meta.url),
    );
    return mergeConfig(vite, {
      plugins: [tailwind()],
      server: { fs: { allow: [repoRoot] } },
      resolve: {
        alias: {
          "@storybook/react": storybookReact,
          "@storybook/test": storybookTest,
        },
      },
    });
  },
};

export default config;
