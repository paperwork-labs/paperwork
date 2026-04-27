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
          "text-faint": "rgb(var(--brand-text-faint) / <alpha-value>)",
          "text-subtle": "rgb(var(--brand-text-subtle) / <alpha-value>)",
          border: "rgb(var(--brand-border) / <alpha-value>)",
          "metric-up": "rgb(var(--brand-metric-up) / <alpha-value>)",
        },
      },
    },
  },
} satisfies Config;
