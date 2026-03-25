import { createSystem, defaultConfig, defineConfig, defineRecipe } from "@chakra-ui/react";

const buttonRecipe = defineRecipe({
  base: {
    borderRadius: "lg",
    fontWeight: "semibold",
    letterSpacing: "-0.01em",
    cursor: "pointer",
    transition: "all 200ms ease",
    _focusVisible: {
      boxShadow: "0 0 0 3px var(--chakra-colors-focusRing)",
      outline: "none",
    },
    _disabled: {
      opacity: 0.5,
      cursor: "not-allowed",
      transform: "none",
    },
    _hover: {
      transform: "translateY(-1px)",
    },
    _active: {
      transform: "translateY(0)",
    },
  },
});

const inputRecipe = defineRecipe({
  base: {
    borderRadius: "lg",
    bg: "bg.input",
    borderColor: "border.subtle",
    transition: "border-color 200ms ease, box-shadow 200ms ease",
    _placeholder: { color: "fg.subtle" },
    _focusVisible: {
      borderColor: "amber.500",
      boxShadow: "0 0 0 3px var(--chakra-colors-focusRing)",
      outline: "none",
    },
  },
});

export const system = createSystem(
  defaultConfig,
  defineConfig({
    globalCss: {
      "html, body, #root": {
        height: "100%",
        backgroundColor: "bg.canvas",
        color: "fg.default",
      },
      "@media (prefers-reduced-motion: reduce)": {
        // @ts-expect-error — selector string not in SystemStyleObject index
        "*, *::before, *::after": {
          animationDuration: "0.01ms !important",
          animationIterationCount: "1 !important",
          transitionDuration: "0.01ms !important",
          scrollBehavior: "auto !important",
        },
      },
    },
    theme: {
      tokens: {
        colors: {
          brand: {
            50: { value: "#EFF6FF" },
            100: { value: "#DBEAFE" },
            200: { value: "#BFDBFE" },
            300: { value: "#93C5FD" },
            400: { value: "#60A5FA" },
            500: { value: "#3B82F6" },
            600: { value: "#2563EB" },
            700: { value: "#1D4ED8" },
            800: { value: "#1E40AF" },
            900: { value: "#1E3A8A" },
          },
          accent: {
            50: { value: "#F0FDF4" },
            100: { value: "#DCFCE7" },
            200: { value: "#BBF7D0" },
            300: { value: "#86EFAC" },
            400: { value: "#4ADE80" },
            500: { value: "#22C55E" },
            600: { value: "#16A34A" },
            700: { value: "#15803D" },
            800: { value: "#166534" },
            900: { value: "#14532D" },
          },
          amber: {
            50: { value: "#FFFBEB" },
            100: { value: "#FEF3C7" },
            200: { value: "#FDE68A" },
            300: { value: "#FCD34D" },
            400: { value: "#FBBF24" },
            500: { value: "#F59E0B" },
            600: { value: "#D97706" },
            700: { value: "#B45309" },
            800: { value: "#92400E" },
            900: { value: "#78350F" },
          },
          focusRing: { value: "rgba(245,158,11,0.25)" },
        },
        fonts: {
          heading: {
            value:
              "'IBM Plex Sans', 'Inter', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial",
          },
          body: {
            value: "'Inter', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial",
          },
          mono: {
            value:
              "'JetBrains Mono', 'Fira Code', 'SF Mono', 'Cascadia Code', ui-monospace, monospace",
          },
        },
        radii: {
          lg: { value: "10px" },
          xl: { value: "14px" },
        },
      },
      semanticTokens: {
        colors: {
          "bg.canvas": {
            value: { _light: "#F8FAFC", _dark: "#020617" },
          },
          "bg.panel": {
            value: { _light: "white", _dark: "#0F172A" },
          },
          "bg.card": {
            value: { _light: "white", _dark: "#111827" },
          },
          "bg.muted": {
            value: {
              _light: "rgba(15, 23, 42, 0.04)",
              _dark: "rgba(255, 255, 255, 0.05)",
            },
          },
          "bg.subtle": {
            value: {
              _light: "rgba(15, 23, 42, 0.06)",
              _dark: "rgba(255, 255, 255, 0.08)",
            },
          },
          "bg.elevated": {
            value: { _light: "white", _dark: "#1E293B" },
          },
          "bg.header": {
            value: { _light: "white", _dark: "#0F172A" },
          },
          "bg.sidebar": {
            value: { _light: "white", _dark: "#0F172A" },
          },
          "bg.input": {
            value: {
              _light: "rgba(0,0,0,0.03)",
              _dark: "rgba(0,0,0,0.25)",
            },
          },
          "bg.hover": {
            value: {
              _light: "rgba(15, 23, 42, 0.04)",
              _dark: "rgba(255, 255, 255, 0.04)",
            },
          },
          "fg.default": {
            value: { _light: "#0F172A", _dark: "#F8FAFC" },
          },
          "fg.muted": {
            value: {
              _light: "rgba(15,23,42,0.65)",
              _dark: "rgba(248,250,252,0.68)",
            },
          },
          "fg.subtle": {
            value: {
              _light: "rgba(15,23,42,0.42)",
              _dark: "rgba(248,250,252,0.50)",
            },
          },
          "fg.accent": {
            value: { _light: "#16A34A", _dark: "#22C55E" },
          },
          "fg.amber": {
            value: { _light: "#D97706", _dark: "#F59E0B" },
          },
          "border.subtle": {
            value: {
              _light: "rgba(15,23,42,0.08)",
              _dark: "rgba(255,255,255,0.08)",
            },
          },
          "border.strong": {
            value: {
              _light: "rgba(15,23,42,0.16)",
              _dark: "rgba(255,255,255,0.14)",
            },
          },
          "border.hover": {
            value: {
              _light: "rgba(15,23,42,0.20)",
              _dark: "rgba(255,255,255,0.18)",
            },
          },
          "status.success": {
            value: { _light: "#16A34A", _dark: "#34D399" },
          },
          "status.warning": {
            value: { _light: "#D97706", _dark: "#F59E0B" },
          },
          "status.danger": {
            value: { _light: "#DC2626", _dark: "#F87171" },
          },
          "status.info": {
            value: { _light: "#0EA5E9", _dark: "#38BDF8" },
          },
          "chart.danger": {
            value: { _light: "#DC2626", _dark: "#F87171" },
          },
          "chart.success": {
            value: { _light: "#16A34A", _dark: "#4ADE80" },
          },
          "chart.neutral": {
            value: { _light: "#3B82F6", _dark: "#60A5FA" },
          },
          "chart.area1": {
            value: { _light: "#16A34A", _dark: "#34D399" },
          },
          "chart.area2": {
            value: { _light: "#2563EB", _dark: "#60A5FA" },
          },
          "chart.grid": {
            value: { _light: "rgba(15,23,42,0.06)", _dark: "rgba(255,255,255,0.05)" },
          },
          "chart.axis": {
            value: { _light: "rgba(15,23,42,0.35)", _dark: "rgba(255,255,255,0.40)" },
          },
          "chart.refLine": {
            value: { _light: "rgba(15,23,42,0.15)", _dark: "rgba(255,255,255,0.15)" },
          },
          "chart.warning": {
            value: { _light: "#D97706", _dark: "#FBBF24" },
          },
          "chart.tooltip.bg": {
            value: { _light: "white", _dark: "#1E293B" },
          },
          "chart.tooltip.border": {
            value: {
              _light: "rgba(15,23,42,0.10)",
              _dark: "rgba(255,255,255,0.10)",
            },
          },
          "glow.accent": {
            value: {
              _light: "rgba(34,197,94,0)",
              _dark: "rgba(34,197,94,0.12)",
            },
          },
          "glow.amber": {
            value: {
              _light: "rgba(245,158,11,0)",
              _dark: "rgba(245,158,11,0.10)",
            },
          },
          "glow.brand": {
            value: {
              _light: "rgba(59,130,246,0)",
              _dark: "rgba(59,130,246,0.10)",
            },
          },
        },
      },
      recipes: {
        button: buttonRecipe,
        input: inputRecipe,
      },
    },
  })
);
