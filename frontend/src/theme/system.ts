import { createSystem, defaultConfig, defineConfig, defineRecipe } from "@chakra-ui/react";

// Snowball-ish + Apple-ish: subtle radii, crisp focus, quiet surfaces.
const buttonRecipe = defineRecipe({
  base: {
    borderRadius: "lg",
    fontWeight: "semibold",
    letterSpacing: "-0.01em",
    _focusVisible: {
      boxShadow: "0 0 0 4px var(--chakra-colors-focusRing)",
    },
    _disabled: {
      opacity: 0.6,
      cursor: "not-allowed",
    },
  },
});

const inputRecipe = defineRecipe({
  base: {
    borderRadius: "lg",
    bg: "bg.input",
    borderColor: "border.subtle",
    _placeholder: { color: "fg.subtle" },
    _focusVisible: {
      borderColor: "brand.500",
      boxShadow: "0 0 0 4px var(--chakra-colors-focusRing)",
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
      body: {
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
          // Used for focus ring in recipes.
          focusRing: { value: "rgba(29,78,216,0.22)" },
        },
        fonts: {
          heading: {
            value:
              "'Space Grotesk', 'Inter', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial",
          },
          body: {
            value: "'Inter', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial",
          },
        },
        radii: {
          lg: { value: "12px" },
          xl: { value: "16px" },
        },
      },
      semanticTokens: {
        colors: {
          "bg.canvas": {
            value: {
              _light: "#F8FAFC",
              _dark: "#0F172A",
            },
          },
          // Slightly elevated surface behind cards/tables.
          "bg.panel": {
            value: {
              _light: "white",
              _dark: "#1E293B",
            },
          },
          "bg.card": {
            value: {
              _light: "white",
              _dark: "rgba(17, 24, 39, 0.72)",
            },
          },
          // Subtle interactive surfaces (hover/selected states).
          "bg.muted": {
            value: {
              _light: "rgba(15, 23, 42, 0.05)",
              _dark: "rgba(255, 255, 255, 0.06)",
            },
          },
          "bg.subtle": {
            value: {
              _light: "rgba(15, 23, 42, 0.08)",
              _dark: "rgba(255, 255, 255, 0.10)",
            },
          },
          // Layout surfaces (header/sidebar) so app chrome theme stays coherent.
          "bg.header": {
            value: {
              _light: "white",
              _dark: "#1E293B",
            },
          },
          "bg.sidebar": {
            value: {
              _light: "white",
              _dark: "#1E293B",
            },
          },
          "bg.input": {
            value: {
              _light: "rgba(0,0,0,0.03)",
              _dark: "rgba(0,0,0,0.25)",
            },
          },
          "fg.default": {
            value: {
              _light: "#111827",
              _dark: "rgba(255,255,255,0.92)",
            },
          },
          "fg.muted": {
            value: {
              _light: "rgba(11,18,32,0.68)",
              _dark: "rgba(255,255,255,0.70)",
            },
          },
          "fg.subtle": {
            value: {
              _light: "rgba(11,18,32,0.46)",
              _dark: "rgba(255,255,255,0.55)",
            },
          },
          "border.subtle": {
            value: {
              _light: "rgba(15,23,42,0.10)",
              _dark: "rgba(255,255,255,0.12)",
            },
          },
          "border.strong": {
            value: {
              _light: "rgba(15,23,42,0.18)",
              _dark: "rgba(255,255,255,0.18)",
            },
          },
          "status.success": {
            value: {
              _light: "#16A34A",
              _dark: "#34D399",
            },
          },
          "status.warning": {
            value: {
              _light: "#D97706",
              _dark: "#F59E0B",
            },
          },
          "status.danger": {
            value: {
              _light: "#DC2626",
              _dark: "#F87171",
            },
          },
          "status.info": {
            value: {
              _light: "#0EA5E9",
              _dark: "#38BDF8",
            },
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
            value: { _light: "rgba(15,23,42,0.08)", _dark: "rgba(255,255,255,0.08)" },
          },
          "chart.axis": {
            value: { _light: "rgba(15,23,42,0.4)", _dark: "rgba(255,255,255,0.45)" },
          },
          "chart.refLine": {
            value: { _light: "rgba(15,23,42,0.2)", _dark: "rgba(255,255,255,0.2)" },
          },
          "chart.warning": {
            value: { _light: "#D97706", _dark: "#FBBF24" },
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


