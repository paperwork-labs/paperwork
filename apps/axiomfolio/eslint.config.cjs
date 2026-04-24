const tseslint = require("@typescript-eslint/eslint-plugin");
const tsParser = require("@typescript-eslint/parser");
const reactHooks = require("eslint-plugin-react-hooks");
const reactRefresh = require("eslint-plugin-react-refresh");

/** @type {import("eslint").Linter.FlatConfig[]} */
module.exports = [
  {
    ignores: ["dist/**", "build/**", "node_modules/**"],
  },
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      "@typescript-eslint": tseslint,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      // Keep this intentionally lightweight (no type-aware linting),
      // so it works across Vite/Ladle/Vitest files without tsconfig project wiring.
      ...(tseslint.configs.recommended?.rules ?? {}),
      // Only enforce the core hooks rule. (The newer plugin ships additional
      // "react-hooks/*" rules that are too strict for the current codebase.)
      "react-hooks/rules-of-hooks": "error",

      // Existing codebase uses `any` in a few places; type-checking is enforced via `npm run type-check`.
      "@typescript-eslint/no-explicit-any": "off",

      // Avoid churn: allow unused vars (TS compiler catches many cases; tests may stub args).
      "@typescript-eslint/no-unused-vars": "off",

      // Helps ensure fast refresh works correctly in development
      // (Disabled for now to avoid warnings failing CI; we can tighten later.)
      "react-refresh/only-export-components": "off",

      // Avoid CI noise; we can tighten with targeted fixes later.
      "react-hooks/exhaustive-deps": "off",
    },
  },
];


