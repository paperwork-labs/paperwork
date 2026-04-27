import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Used if tooling runs Vite directly; Storybook merges Tailwind in `.storybook/main.ts` `viteFinal`.
export default defineConfig({
  plugins: [react(), tailwindcss()],
});
