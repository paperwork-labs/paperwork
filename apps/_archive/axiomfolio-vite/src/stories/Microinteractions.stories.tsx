import * as React from "react";

import {
  ChartCrosshair,
  useCrosshairTracking,
} from "../components/charts/ChartCrosshair";
import { ErrorState } from "../components/ui/ErrorState";
import { RichTooltip } from "../components/ui/RichTooltip";
import { SegmentedPeriodSelector } from "../components/ui/SegmentedPeriodSelector";
import { ChartGlassCard } from "../components/ui/ChartGlassCard";

export default {
  title: "DesignSystem/Microinteractions",
};

const PERIODS = [
  { value: "1D", label: "1D" },
  { value: "1W", label: "1W" },
  { value: "1M", label: "1M" },
  { value: "3M", label: "3M" },
  { value: "6M", label: "6M" },
  { value: "1Y", label: "1Y" },
  { value: "ALL", label: "ALL" },
] as const;

export const SegmentedSmall = () => {
  const [v, setV] = React.useState<string>("1M");
  return (
    <div className="p-8">
      <SegmentedPeriodSelector
        ariaLabel="Time period (small)"
        size="sm"
        options={PERIODS}
        value={v}
        onChange={setV}
      />
    </div>
  );
};

export const SegmentedMedium = () => {
  const [v, setV] = React.useState<string>("3M");
  return (
    <div className="p-8">
      <SegmentedPeriodSelector
        ariaLabel="Time period (medium)"
        size="md"
        options={PERIODS}
        value={v}
        onChange={setV}
      />
      <p className="mt-4 text-xs text-muted-foreground">
        Try ArrowLeft / ArrowRight, Home, End for keyboard navigation.
      </p>
    </div>
  );
};

export const RichTooltipHover = () => (
  <div className="flex flex-wrap items-center gap-8 p-12">
    {(["top", "right", "bottom", "left"] as const).map((side) => (
      <RichTooltip
        key={side}
        side={side}
        trigger={
          <button
            type="button"
            className="rounded-md border border-border bg-card px-3 py-1.5 text-sm"
          >
            Hover ({side})
          </button>
        }
      >
        <div className="text-xs">
          <p className="font-medium text-foreground">AAPL · Apple Inc.</p>
          <p className="mt-1 text-muted-foreground">
            Stage 2A · RS 1.32 · ATR 3.4%
          </p>
        </div>
      </RichTooltip>
    ))}
  </div>
);

export const RichTooltipClick = () => (
  <div className="p-12">
    <RichTooltip
      openOn="click"
      side="bottom"
      trigger={
        <button
          type="button"
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm"
        >
          Click to open
        </button>
      }
    >
      <div className="text-xs">
        <p className="font-medium text-foreground">Position details</p>
        <p className="mt-1 text-muted-foreground">
          Click anywhere outside this card to dismiss.
        </p>
      </div>
    </RichTooltip>
  </div>
);

export const Crosshair = () => {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const [size, setSize] = React.useState({ w: 600, h: 280 });
  const { x, y, onMouseMove, onMouseLeave } = useCrosshairTracking();

  React.useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const cr = e.contentRect;
        setSize({ w: Math.round(cr.width), h: Math.round(cr.height) });
      }
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="p-8">
      <ChartGlassCard ariaLabel="Crosshair demo">
        <div
          ref={ref}
          className="relative h-[280px] w-full overflow-hidden rounded-md bg-muted/40"
          onMouseMove={onMouseMove}
          onMouseLeave={onMouseLeave}
        >
          <div className="grid h-full place-items-center text-xs text-muted-foreground">
            Move your pointer over this card.
          </div>
          <ChartCrosshair
            width={size.w}
            height={size.h}
            x={x}
            y={y}
            announceText={
              x !== null && y !== null
                ? `Pointer at ${Math.round(x)}, ${Math.round(y)}`
                : undefined
            }
          />
        </div>
      </ChartGlassCard>
    </div>
  );
};

export const ErrorStateDemo = () => (
  <div className="p-12">
    <ErrorState
      title="Couldn't load market snapshot"
      description="The market data service is unreachable. Try again, or check the operator dashboard for pipeline status."
      retry={() => {
        /* demo only */
      }}
      error={new Error("ECONNREFUSED — backend at /api/v1/market-data/...")}
    />
  </div>
);

export const FocusRing = () => (
  <div className="flex flex-col gap-3 p-12">
    <p className="text-xs text-muted-foreground">
      Tab through these — every focusable element should get a 2px polished
      ring via the global `:focus-visible` baseline.
    </p>
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" className="rounded-md border border-border bg-card px-3 py-1.5 text-sm">
        Naked button
      </button>
      <a
        href="#focus-demo"
        className="rounded-md border border-border bg-card px-3 py-1.5 text-sm"
      >
        Naked anchor
      </a>
      <input
        type="text"
        placeholder="Naked input"
        className="rounded-md border border-border bg-card px-3 py-1.5 text-sm"
      />
      <select className="rounded-md border border-border bg-card px-3 py-1.5 text-sm">
        <option>Option A</option>
        <option>Option B</option>
      </select>
      <span tabIndex={0} className="rounded-md border border-border bg-card px-3 py-1.5 text-sm">
        tabindex span
      </span>
    </div>
  </div>
);
