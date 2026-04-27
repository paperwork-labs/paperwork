import * as React from "react";

import type { Preview } from "@storybook/react";
import { withThemeByClassName } from "@storybook/addon-themes";

import { ColorModeProvider } from "@axiomfolio/theme/colorMode";

import "./preview.css";

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    backgrounds: {
      default: "slate-night",
      values: [
        { name: "light", value: "#F8FAFC" },
        { name: "slate-night", value: "#0F172A" },
        { name: "white", value: "#FFFFFF" },
        { name: "transparent", value: "transparent" },
      ],
    },
    viewport: {
      viewports: {
        favicon16: {
          name: "Favicon 16",
          styles: { width: "16px", height: "16px" },
          type: "other",
        },
        favicon32: {
          name: "Favicon 32",
          styles: { width: "32px", height: "32px" },
          type: "other",
        },
        favicon48: {
          name: "Favicon 48",
          styles: { width: "48px", height: "48px" },
          type: "other",
        },
        mobile320: {
          name: "Mobile (320)",
          styles: { width: "320px", height: "568px" },
          type: "mobile",
        },
        tablet768: {
          name: "Tablet (768)",
          styles: { width: "768px", height: "1024px" },
          type: "tablet",
        },
        desktop1280: {
          name: "Desktop (1280)",
          styles: { width: "1280px", height: "800px" },
          type: "desktop",
        },
        desktop1920: {
          name: "Desktop (1920)",
          styles: { width: "1920px", height: "1080px" },
          type: "desktop",
        },
      },
    },
    a11y: {
      // Run axe at canvas-load and re-run on story switch.
      test: "todo",
    },
    options: {
      storySort: {
        order: [
          "Brand",
          ["Paperwork Labs", "AxiomFolio"],
          "DesignSystem",
          ["Tokens", "Foundation", "Motion", "Microinteractions", "*"],
          "Components",
          "Charts",
          "Tables",
          "*",
        ],
      },
    },
  },
  decorators: [
    withThemeByClassName({
      themes: {
        light: "light",
        dark: "dark",
      },
      defaultTheme: "dark",
      parentSelector: "html",
    }),
    (Story) => (
      <ColorModeProvider>
        <div
          style={{
            minHeight: "100vh",
            color: "var(--foreground, #0F172A)",
            background: "var(--background, transparent)",
          }}
        >
          <Story />
        </div>
      </ColorModeProvider>
    ),
  ],
};

export default preview;
