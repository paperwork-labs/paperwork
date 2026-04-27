import React from "react";

import { ChartGlassCard } from "@axiomfolio/components/ui/ChartGlassCard";
import { setColorPalettePreference } from "@axiomfolio/hooks/useUserPreferences";
import { getSeriesPalette } from "@axiomfolio/constants/chart";
import type { Meta, StoryObj } from "@storybook/react";

const meta: Meta = {
  title: "DesignSystem/Foundation",
};
export default meta;

type Story = StoryObj;

const Swatch = ({ color, label }: { color: string; label: string }) => (
  <div className="flex flex-col items-stretch overflow-hidden rounded-lg border border-border bg-card">
    <div className="h-12" style={{ background: color }} />
    <div className="flex flex-col gap-0.5 p-3">
      <span className="text-xs font-medium text-foreground">{label}</span>
      <code className="text-[11px] text-muted-foreground">{color}</code>
    </div>
  </div>
);

const PaletteRow = ({ heading }: { heading: string }) => {
  const colors = getSeriesPalette();
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-sm font-medium text-foreground">{heading}</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-8">
        {colors.map((c, i) => (
          <Swatch key={i} color={c} label={`series-${i + 1}`} />
        ))}
      </div>
    </section>
  );
};

export const Typography: Story = {
  render: () => (
  <div className="flex flex-col gap-6 p-6 text-foreground">
    <div>
      <p className="text-xs uppercase tracking-wider text-muted-foreground">
        Geist Sans (UI)
      </p>
      <p className="text-4xl font-semibold leading-tight">
        AxiomFolio — quant-grade portfolio intelligence.
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        The quick brown fox jumps over the lazy dog. 0123456789
      </p>
    </div>
    <div>
      <p className="text-xs uppercase tracking-wider text-muted-foreground">
        Geist Mono (tabular numbers)
      </p>
      <p className="font-mono text-2xl tabular-nums">
        $123,456.78 · +2.34% · 1.2M shares
      </p>
    </div>
    <div>
      <p className="text-xs uppercase tracking-wider text-muted-foreground">
        Tabular numerics in flowing text
      </p>
      <p className="text-base tabular-nums">
        AAPL closed at $189.34 (+1.12%) on volume of 51,234,567 shares,
        a 2.4× pickup over the 50-day average.
      </p>
    </div>
  </div>
),
};

export const SeriesPaletteDefault: Story = {
  render: () => (
  <div className="flex flex-col gap-6 p-6">
    <PaletteRow heading="Default series palette (theme-aware)" />
  </div>
),
};

export const SeriesPaletteColorBlind: Story = {
  render: () => {
  React.useEffect(() => {
    // Capture the developer's pre-existing preference so we restore it on
    // unmount instead of clobbering it back to "default". Reading directly
    // from localStorage avoids importing a private accessor from the hook.
    const previous =
      (typeof window !== "undefined" &&
        window.localStorage.getItem("axiomfolio:color-palette")) ||
      "default";
    setColorPalettePreference("cb");
    return () => {
      setColorPalettePreference(previous === "cb" ? "cb" : "default");
    };
  }, []);
  return (
    <div className="flex flex-col gap-6 p-6">
      <PaletteRow heading="Okabe-Ito 2008 (color-blind safe)" />
    </div>
  );
},
};

export const Elevation: Story = {
  render: () => {
  const levels = ["resting", "hover", "active", "floating"] as const;
  return (
    <div className="grid grid-cols-1 gap-6 p-6 md:grid-cols-2 xl:grid-cols-4">
      {levels.map((level) => (
        <ChartGlassCard key={level} level={level} ariaLabel={`${level} card`}>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            level
          </p>
          <p className="font-mono text-lg text-foreground">{level}</p>
          <p className="mt-2 text-sm text-muted-foreground">
            {`shadow-[var(--shadow-${level})]`}
          </p>
        </ChartGlassCard>
      ))}
    </div>
  );
},
};

export const GlassSurface: Story = {
  render: () => (
  <div className="relative min-h-[420px] overflow-hidden rounded-2xl bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 p-12">
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <ChartGlassCard glass level="hover" ariaLabel="Frosted glass card">
        <p className="text-sm font-medium text-foreground">Frosted glass</p>
        <p className="mt-1 text-sm text-muted-foreground">
          backdrop-blur-xl + 70% bg-card. Sits cleanly over any background.
        </p>
      </ChartGlassCard>
      <ChartGlassCard glass level="floating" ariaLabel="Floating glass card">
        <p className="text-sm font-medium text-foreground">Floating + glass</p>
        <p className="mt-1 text-sm text-muted-foreground">
          For share previews, OG image generators, modal-adjacent surfaces.
        </p>
      </ChartGlassCard>
    </div>
  </div>
),
};

export const Selection: Story = {
  render: () => (
  <div className="p-6 text-foreground">
    <p className="text-xs uppercase tracking-wider text-muted-foreground">
      Try selecting any of this text — selection is brand-tinted.
    </p>
    <p className="mt-2 max-w-prose text-base leading-relaxed">
      One trait of premium UIs is a selection color that matches the brand
      instead of the OS default. We use a 18% blue tint in light mode and
      28% in dark mode, with foreground that always passes WCAG contrast.
    </p>
  </div>
),
};
