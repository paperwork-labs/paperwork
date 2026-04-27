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
        },
      },
    },
  },
} satisfies Config;

