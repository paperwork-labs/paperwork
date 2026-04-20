import * as React from "react";
import { AnimatePresence } from "framer-motion";

import { AnimatedNumber } from "../components/ui/AnimatedNumber";
import { Button } from "../components/ui/button";
import {
  EquityCurveSkeleton,
  MetricStripSkeleton,
  PriceChartSkeleton,
  TreemapSkeleton,
} from "../components/charts/skeletons";
import { PageTransition } from "../components/transitions/PageTransition";

export default {
  title: "DesignSystem/Motion",
};

const Section: React.FC<
  React.PropsWithChildren<{ title: string; subtitle?: string }>
> = ({ title, subtitle, children }) => (
  <section className="flex flex-col gap-3">
    <header className="flex flex-col gap-1">
      <h3 className="text-sm font-medium text-foreground">{title}</h3>
      {subtitle ? (
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      ) : null}
    </header>
    <div>{children}</div>
  </section>
);

export const AnimatedNumberDemo = () => {
  const [value, setValue] = React.useState(1234.56);
  return (
    <div className="flex flex-col gap-6 p-6 text-foreground">
      <Section
        title="AnimatedNumber"
        subtitle="Spring tween between numeric values. Always tabular-nums."
      >
        <div className="flex items-baseline gap-3">
          <span className="text-4xl font-semibold">$</span>
          <AnimatedNumber
            value={value}
            className="text-4xl font-semibold"
            format={(n) =>
              n.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })
            }
            ariaLabel={`portfolio value ${value.toFixed(2)} dollars`}
          />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => setValue((v) => v - 250)}>−250</Button>
          <Button onClick={() => setValue((v) => v - 25)}>−25</Button>
          <Button onClick={() => setValue((v) => v + 25)}>+25</Button>
          <Button onClick={() => setValue((v) => v + 250)}>+250</Button>
          <Button
            variant="secondary"
            onClick={() =>
              setValue(Math.round(Math.random() * 100000) / 100)
            }
          >
            Randomize
          </Button>
        </div>
      </Section>
    </div>
  );
};

export const ChartSkeletons = () => (
  <div className="flex flex-col gap-8 p-6">
    <Section
      title="MetricStripSkeleton"
      subtitle="Use above charts while KPI tiles load."
    >
      <MetricStripSkeleton />
    </Section>
    <Section
      title="PriceChartSkeleton"
      subtitle="Default 380px height. Ghost line traces gently to communicate loading."
    >
      <PriceChartSkeleton />
    </Section>
    <Section
      title="EquityCurveSkeleton"
      subtitle="Equity curve + drawdown sub-chart. Default 420px height."
    >
      <EquityCurveSkeleton />
    </Section>
    <Section
      title="TreemapSkeleton"
      subtitle="Deterministic 4×3 grid (no Math.random — SSR / snapshot stable)."
    >
      <TreemapSkeleton />
    </Section>
  </div>
);

export const PageTransitionDemo = () => {
  const [page, setPage] = React.useState<"a" | "b">("a");
  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex gap-2">
        <Button
          variant={page === "a" ? "default" : "secondary"}
          onClick={() => setPage("a")}
        >
          Page A
        </Button>
        <Button
          variant={page === "b" ? "default" : "secondary"}
          onClick={() => setPage("b")}
        >
          Page B
        </Button>
      </div>
      <div className="relative min-h-[200px] overflow-hidden rounded-lg border border-border bg-card p-6">
        <AnimatePresence mode="wait">
          <PageTransition key={page}>
            <h2 className="text-2xl font-semibold text-foreground">
              {page === "a" ? "Page A" : "Page B"}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Toggle the buttons above to swap routes. The PageTransition
              wrapper handles the slide-up + fade entry; AnimatePresence
              with <code>mode=&quot;wait&quot;</code> sequences the exit
              before the next mount.
            </p>
          </PageTransition>
        </AnimatePresence>
      </div>
    </div>
  );
};
