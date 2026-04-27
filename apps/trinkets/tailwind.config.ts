import type { Config } from "tailwindcss";

export default {
  theme: {
    extend: {
      colors: {
        brand: {
          primary: "rgb(var(--brand-primary) / <alpha-value>)",
          accent: "rgb(var(--brand-accent) / <alpha-value>)",
          ink: "rgb(var(--brand-ink) / <alpha-value>)",
          surface: "rgb(var(--brand-surface) / <alpha-value>)",
          "surface-elevated": "rgb(var(--brand-surface-elevated) / <alpha-value>)",
          text: "rgb(var(--brand-ink) / <alpha-value>)",
          "text-muted": "rgb(var(--brand-text-muted) / <alpha-value>)",
          border: "rgb(var(--brand-border) / <alpha-value>)",
        },
      },
    },
  },
} satisfies Config;
