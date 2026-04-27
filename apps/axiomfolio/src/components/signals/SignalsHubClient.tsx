import type { LucideIcon } from "lucide-react";
import { ArrowRight, ClipboardList, Compass, Gauge, Sparkles } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardHeader } from "@/components/ui/card";

type Surface = {
  key: string;
  label: string;
  description: string;
  href: string;
  icon: LucideIcon;
};

const SURFACES: Surface[] = [
  {
    key: "candidates",
    label: "Candidates",
    description:
      "Today's system-generated trade candidates, ranked by pick-quality score. New each trading day.",
    href: "/signals/candidates",
    icon: Sparkles,
  },
  {
    key: "regime",
    label: "Regime",
    description:
      "R1–R5 market regime state with the six-input breakdown and the last 60 days of history.",
    href: "/signals/regime",
    icon: Gauge,
  },
  {
    key: "scan",
    label: "Stage Scan",
    description:
      "Symbols filtered by Weinstein stage and sorted by Mansfield relative strength.",
    href: "/signals/stage-scan",
    icon: Compass,
  },
  {
    key: "picks",
    label: "Picks",
    description:
      "Validator-published picks from external sources, deduplicated and tagged with action.",
    href: "/signals/picks",
    icon: ClipboardList,
  },
];

export function SignalsHubClient() {
  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4">
      <header className="space-y-1">
        <h1 className="font-heading text-xl font-semibold tracking-tight">Signals</h1>
        <p className="text-sm text-muted-foreground">
          Short-form surfaces that translate the indicator layer into decisions. Each page is a
          live view of the backend — nothing here is cached on the client longer than the
          underlying pipeline refresh cycle.
        </p>
      </header>

      <div className="grid gap-3 sm:grid-cols-2">
        {SURFACES.map((surface) => {
          const Icon = surface.icon;
          return (
            <Link
              key={surface.key}
              href={surface.href}
              className="group block rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Card className="h-full transition-colors group-hover:border-primary/40">
                <CardHeader className="flex flex-row items-start gap-3 pb-2">
                  <Icon className="mt-0.5 size-5 text-primary" aria-hidden />
                  <div className="flex-1">
                    <p className="flex items-center justify-between font-medium text-foreground">
                      {surface.label}
                      <ArrowRight
                        className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                        aria-hidden
                      />
                    </p>
                  </div>
                </CardHeader>
                <CardContent className="pt-0 text-sm text-muted-foreground">
                  {surface.description}
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
