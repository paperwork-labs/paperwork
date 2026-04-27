import React from "react";
import { useColorMode } from "@axiomfolio/theme/colorMode";
import AppLogo from "@axiomfolio/components/ui/AppLogo";
import lockupLogo from "@axiomfolio/assets/logos/axiomfolio-lockup.svg";
import lockupDarkLogo from "@axiomfolio/assets/logos/axiomfolio-lockup-dark.svg";
import lockupSurfaceLogo from "@axiomfolio/assets/logos/axiomfolio-lockup-surface.svg";
import starIcon from "@axiomfolio/assets/logos/axiomfolio-icon-star.svg";
import { swatchBackgroundCss } from "./tokenSwatchCss";
import type { Meta, StoryObj } from "@storybook/react";

const meta: Meta = {
  title: "Brand/AxiomFolio",
};
export default meta;

type Story = StoryObj;

const Swatch = ({ name, value }: { name: string; value: string }) => (
  <div className="overflow-hidden rounded-lg border border-border bg-card">
    <div className="h-11" style={{ background: swatchBackgroundCss(value) }} />
    <div className="p-3">
      <div className="text-sm text-foreground">{name}</div>
      <code className="text-xs text-muted-foreground">{value}</code>
    </div>
  </div>
);

export const Overview: Story = {
  render: () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const brandTokens = [
    ["brand.700 (primary)", "brand.700"],
    ["brand.600 (secondary)", "brand.600"],
    ["brand.500", "brand.500"],
    ["brand.400 (dark primary)", "brand.400"],
    ["Canvas", "bg.canvas"],
    ["Panel", "bg.panel"],
    ["Text", "fg.default"],
  ] as const;

  return (
    <div className="p-6">
      <div className="mb-6 flex flex-row items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-foreground">AxiomFolio brand</div>
          <div className="text-sm text-muted-foreground">Mode: {colorMode}</div>
        </div>
        <button
          type="button"
          onClick={toggleColorMode}
          className="rounded-[10px] border border-border px-3 py-2 text-sm"
        >
          Toggle mode
        </button>
      </div>

      <div className="flex flex-col gap-8 items-stretch">
        {/* --- Brand mark (the logo) --- */}
        <div>
          <div className="mb-3 text-sm font-semibold uppercase text-muted-foreground">
            Brand mark (the logo)
          </div>
          <p className="mb-4 text-xs text-muted-foreground">
            The four-point star IS the logo. It renders via {"<AppLogo />"} and uses fixed colors that work on both light and dark backgrounds (no theme switching).
          </p>
          <div className="flex flex-row flex-wrap items-end gap-6">
            <div className="flex flex-col gap-1 items-center">
              <AppLogo size={64} />
              <span className="text-xs text-muted-foreground">64px</span>
            </div>
            <div className="flex flex-col gap-1 items-center">
              <AppLogo size={48} />
              <span className="text-xs text-muted-foreground">48px</span>
            </div>
            <div className="flex flex-col gap-1 items-center">
              <AppLogo size={36} />
              <span className="text-xs text-muted-foreground">36px</span>
            </div>
            <div className="flex flex-col gap-1 items-center">
              <AppLogo size={24} />
              <span className="text-xs text-muted-foreground">24px</span>
            </div>
          </div>
        </div>

        {/* --- Product name alongside mark --- */}
        <div>
          <div className="mb-3 text-sm font-semibold uppercase text-muted-foreground">
            Mark + product name (usage examples)
          </div>
          <p className="mb-4 text-xs text-muted-foreground">
            &quot;AxiomFolio&quot; is the product name — not part of the logo. Render it as separate text alongside the mark.
          </p>
          <div className="flex flex-col gap-4 items-start">
            <div className="flex flex-row items-center gap-[14px]">
              <AppLogo size={52} />
              <span className="text-base font-semibold tracking-tight text-foreground">AxiomFolio</span>
            </div>
            <div className="flex flex-row items-center gap-2.5">
              <AppLogo size={36} />
              <span className="text-sm font-semibold tracking-tight text-foreground">AxiomFolio</span>
            </div>
          </div>
        </div>

        {/* --- Static SVG assets --- */}
        <div>
          <div className="mb-3 text-sm font-semibold uppercase text-muted-foreground">
            Static SVG assets
          </div>
          <p className="mb-4 text-xs text-muted-foreground">
            For external use (docs, marketing, social). The lockups bake in the product name for contexts where the React component isn&apos;t available.
          </p>
          <div className="flex flex-col gap-4 items-stretch">
            <div className="flex flex-row flex-wrap gap-4 items-start">
              <div className="inline-block rounded-lg border border-border bg-background p-4">
                <img src={lockupLogo} alt="Lockup (light)" className="h-12 w-auto" />
              </div>
              <div className="inline-block rounded-lg bg-[#0F172A] p-4">
                <img src={lockupDarkLogo} alt="Lockup (dark)" className="h-12 w-auto" />
              </div>
            </div>
            <div className="inline-block rounded-lg bg-[#0F172A] p-4">
              <img src={lockupSurfaceLogo} alt="Lockup on surface chip" className="h-14 w-auto" />
            </div>
            <div className="flex flex-row gap-4">
              <div className="inline-block rounded-lg border border-border bg-background p-3">
                <img src={starIcon} alt="Star mark (light)" className="size-12" />
              </div>
              <div className="inline-block rounded-lg bg-[#0F172A] p-3">
                <img src={starIcon} alt="Star mark (dark)" className="size-12" />
              </div>
            </div>
          </div>
        </div>

        {/* --- Palette --- */}
        <div>
          <div className="mb-3 text-sm font-semibold uppercase text-muted-foreground">
            Brand palette
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
            {brandTokens.map(([name, value]) => (
              <Swatch key={name} name={name} value={value} />
            ))}
          </div>
        </div>

        <div>
          <div className="mb-3 text-sm font-semibold uppercase text-muted-foreground">
            Status colors
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-4">
            <Swatch name="status.success" value="status.success" />
            <Swatch name="status.warning" value="status.warning" />
            <Swatch name="status.danger" value="status.danger" />
            <Swatch name="status.info" value="status.info" />
          </div>
        </div>

        <div>
          <div className="mb-3 text-sm font-semibold uppercase text-muted-foreground">
            Typography
          </div>
          <div className="flex flex-col gap-2 items-stretch">
            <div className="text-2xl font-semibold text-foreground">
              AxiomFolio: Clarity for modern portfolios
            </div>
            <div className="text-base text-muted-foreground">
              Product UI uses Tailwind CSS v4 and shadcn-style primitives for consistency, scale, and accessibility.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
},
};
