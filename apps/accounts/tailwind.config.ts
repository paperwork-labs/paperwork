import type { Config } from "tailwindcss";

/**
 * Tailwind v4: primary config lives in `src/app/globals.css` (`@import "tailwindcss"`).
 * Content paths remain explicit for editor tooling and any legacy scanners.
 */
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
};

export default config;
