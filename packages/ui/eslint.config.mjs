import eslint from "@eslint/js";
import tseslint from "typescript-eslint";

// Framework-agnostic design system: consumable from Next, Vite, Storybook, RN web.
// See packages/ui/README.md and scripts/check-ui-package-purity.mjs.
export default tseslint.config(
  {
    ignores: ["node_modules/**", "eslint.config.mjs"],
  },
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.ts", "src/**/*.tsx"],
    languageOptions: {
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "off",
    },
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "next",
              message:
                "Do not import `next` from @paperwork-labs/ui; colocate in apps/<name>/.",
            },
            {
              name: "next-auth",
              message:
                "Do not import `next-auth` from @paperwork-labs/ui; use apps/<name>/ or packages/auth/.",
            },
            {
              name: "vite",
              message:
                "Do not import `vite` from @paperwork-labs/ui; Vite config belongs in the app/tooling package.",
            },
            {
              name: "fs",
              message:
                "Do not import Node `fs` from @paperwork-labs/ui; UI must not depend on Node built-ins.",
            },
            {
              name: "path",
              message:
                "Do not import Node `path` from @paperwork-labs/ui; UI must not depend on Node built-ins.",
            },
            {
              name: "child_process",
              message:
                "Do not import `child_process` from @paperwork-labs/ui; UI must not depend on Node built-ins.",
            },
            {
              name: "next/router",
              message:
                "Do not import `next/router` from @paperwork-labs/ui; colocate in the consuming app.",
            },
            {
              name: "next/navigation",
              message:
                "Do not import `next/navigation` from @paperwork-labs/ui; colocate in the consuming app.",
            },
            {
              name: "next/headers",
              message:
                "Do not import `next/headers` from @paperwork-labs/ui; server-only — colocate in app or API.",
            },
            {
              name: "next/image",
              message:
                "Do not import `next/image` from @paperwork-labs/ui; wrap in apps/<name>/ if needed.",
            },
            {
              name: "next/link",
              message:
                "Do not import `next/link` from @paperwork-labs/ui; colocate in the consuming app.",
            },
            {
              name: "react-router",
              message:
                "Do not import `react-router` from @paperwork-labs/ui; colocate in the consumer app.",
            },
            {
              name: "react-router-dom",
              message:
                "Do not import `react-router-dom` from @paperwork-labs/ui; colocate in the consumer app.",
            },
          ],
          patterns: [
            {
              group: ["next/*"],
              message:
                "Do not import from `next/*` in @paperwork-labs/ui; colocate in apps/<name>/src/.",
            },
            {
              group: ["next-auth/*"],
              message:
                "Do not import from `next-auth/*` in @paperwork-labs/ui; colocate in apps/<name>/ or packages/auth/.",
            },
            {
              group: ["node:*"],
              message:
                "Do not import `node:*` built-ins from @paperwork-labs/ui; keep this package browser-safe.",
            },
            {
              group: ["@vercel/*"],
              message:
                "Do not import `@vercel/*` from @paperwork-labs/ui; platform SDKs belong in apps or infra packages.",
            },
          ],
        },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: 'ExpressionStatement > Literal[value="use server"]',
          message:
            'Do not use the "use server" directive in @paperwork-labs/ui; colocate in an app or API surface.',
        },
        {
          selector: "ExportNamedDeclaration > FunctionDeclaration[async=true]",
          message:
            "Do not `export async function` from @paperwork-labs/ui; use sync exports or colocate in the consuming app.",
        },
        {
          selector: "ExportDefaultDeclaration > FunctionDeclaration[async=true]",
          message:
            "Do not `export default async function` from @paperwork-labs/ui; colocate in the consuming app.",
        },
        {
          selector:
            "MemberExpression[object.name='process'][property.name='env']",
          message:
            "Do not read `process.env` in @paperwork-labs/ui; pass configuration via props, React context, or host wrappers.",
        },
      ],
      "no-restricted-globals": [
        "error",
        {
          name: "window",
          message:
            "Avoid unguarded `window` in @paperwork-labs/ui; use `typeof window !== \"undefined\"` before access, `globalThis`, or pass values via props. Prefer a small `useIsomorphicLayoutEffect` helper in the host if needed.",
        },
      ],
    },
  }
);
