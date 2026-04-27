import React from "react";
import { useColorMode } from "@axiomfolio/theme/colorMode";
import { swatchBackgroundCss } from "./tokenSwatchCss";
import type { Meta, StoryObj } from "@storybook/react";

const meta: Meta = {
  title: "DesignSystem/Tokens",
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

export const SemanticTokens: Story = {
  render: () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const tokens = [
    ["bg.canvas", "bg.canvas"],
    ["bg.panel", "bg.panel"],
    ["bg.card", "bg.card"],
    ["bg.input", "bg.input"],
    ["fg.default", "fg.default"],
    ["fg.muted", "fg.muted"],
    ["fg.subtle", "fg.subtle"],
    ["border.subtle", "border.subtle"],
    ["border.strong", "border.strong"],
    ["status.success", "status.success"],
    ["status.warning", "status.warning"],
    ["status.danger", "status.danger"],
    ["status.info", "status.info"],
  ] as const;

  return (
    <div className="p-6">
      <div className="mb-5 flex flex-row items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-foreground">Semantic tokens</div>
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

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        {tokens.map(([name, value]) => (
          <Swatch key={name} name={name} value={value} />
        ))}
      </div>
    </div>
  );
},
};

export const AxiomFolioPalette: Story = {
  render: () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const brandTokens = [
    ["brand.50", "brand.50"],
    ["brand.100", "brand.100"],
    ["brand.200", "brand.200"],
    ["brand.300", "brand.300"],
    ["brand.400 (dark primary)", "brand.400"],
    ["brand.500", "brand.500"],
    ["brand.600 (secondary)", "brand.600"],
    ["brand.700 (light primary)", "brand.700"],
    ["brand.800", "brand.800"],
    ["brand.900", "brand.900"],
    ["focusRing", "focusRing"],
  ] as const;

  return (
    <div className="p-6">
      <div className="mb-5 flex flex-row items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-foreground">AxiomFolio palette</div>
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

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        {brandTokens.map(([name, value]) => (
          <Swatch key={name} name={name} value={value} />
        ))}
      </div>
    </div>
  );
},
};
