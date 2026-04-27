import path from "node:path";
import { fileURLToPath } from "node:url";

import type { StorybookConfig } from "@storybook/react-vite";
import tailwindcss from "@tailwindcss/vite";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../..");
const axiomfolioSrc = path.join(repoRoot, "apps/axiomfolio/src");
const designNodeModules = path.resolve(here, "../node_modules");

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
    // `react-docgen` handles files outside the active tsconfig project (the
    // canvas pulls components from apps/axiomfolio and packages/**, which
    // are not part of apps/design's tsconfig). The TS-flavoured docgen
    // plugin floods the console with "skipping docgen" warnings for every
    // cross-project import; the plain JS docgen reads JSDoc + prop types
    // without that constraint.
    reactDocgen: "react-docgen",
  },
  // Tailwind v4 + cross-app aliases. The design canvas currently sources its
  // stories from apps/axiomfolio/src; mapping `@` and `@axiomfolio` keeps the
  // imports inside the migrated stories portable until each story moves into
  // its owning package.
  viteFinal: async (vite) => {
    vite.plugins = vite.plugins ?? [];
    vite.plugins.push(tailwindcss());

    vite.resolve = vite.resolve ?? {};
    const aliasInput = vite.resolve.alias;
    const aliasMap: Record<string, string> = {
      "@": axiomfolioSrc,
      "@axiomfolio": axiomfolioSrc,
      // AxiomFolio stories/components import `react-router-dom`; Vite must resolve
      // it from the design app install when bundling under `apps/axiomfolio/src`.
      "react-router-dom": path.join(designNodeModules, "react-router-dom"),
    };

    if (Array.isArray(aliasInput)) {
      vite.resolve.alias = [
        ...aliasInput,
        ...Object.entries(aliasMap).map(([find, replacement]) => ({
          find,
          replacement,
        })),
      ];
    } else {
      vite.resolve.alias = { ...(aliasInput ?? {}), ...aliasMap };
    }

    return vite;
  },
};

export default config;
