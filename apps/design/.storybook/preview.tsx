import "@fontsource-variable/inter-tight/wght.css";
import type { Preview } from "@storybook/react";
import { withThemeByClassName } from "@storybook/addon-themes";
import React from "react";

import "../src/styles/preview.css";

const canvasViewports = {
  canvas: {
    name: "Canvas (1200)",
    styles: { width: "1200px", height: "800px" },
  },
  laptop: {
    name: "Laptop",
    styles: { width: "1024px", height: "768px" },
  },
  tablet: {
    name: "Tablet",
    styles: { width: "768px", height: "1024px" },
  },
  mobile: {
    name: "Mobile",
    styles: { width: "390px", height: "844px" },
  },
} as const;

const preview: Preview = {
  parameters: {
    layout: "centered",
    controls: { expanded: true },
    backgrounds: {
      default: "canvas",
      values: [
        { name: "canvas", value: "#f8fafc" },
        { name: "white", value: "#ffffff" },
        { name: "slate-night", value: "#0f172a" },
        { name: "black", value: "#000000" },
      ],
    },
    viewport: {
      viewports: canvasViewports,
      defaultViewport: "canvas",
    },
    a11y: {
      config: {
        rules: [{ id: "color-contrast", enabled: true }],
      },
    },
  },
  decorators: [
    withThemeByClassName({
      themes: {
        light: "",
        dark: "dark",
      },
      defaultTheme: "light",
    }),
    (Story) => (
      <div data-theme="studio" className="min-h-[200px] p-8 text-foreground">
        <Story />
      </div>
    ),
  ],
  initialGlobals: {
    locale: "en",
  },
};

export default preview;
