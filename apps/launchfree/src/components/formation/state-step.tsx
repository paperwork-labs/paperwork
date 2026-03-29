"use client";

import { useFormationStore } from "@/lib/stores/formation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@paperwork-labs/ui";
import { cn } from "@paperwork-labs/ui/lib/utils";
import {
  STATE_FILING_FEES,
  STATE_NAMES,
} from "@paperwork-labs/data/portals/fees";

const POPULAR_STATE_ORDER = [
  "CA",
  "TX",
  "FL",
  "DE",
  "WY",
  "NY",
  "NV",
  "IL",
  "GA",
  "WA",
] as const;

const POPULAR_STATES = POPULAR_STATE_ORDER.map((code) => ({
  code,
  name: STATE_NAMES[code],
  feeCents: STATE_FILING_FEES[code] * 100,
}));

function formatFilingFee(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

export function StateStep() {
  const { data, updateData, nextStep } = useFormationStore();

  const handleSelectState = (stateCode: string) => {
    updateData({ stateCode });
    nextStep();
  };

  return (
    <div className="space-y-8 rounded-xl bg-slate-900 p-6 text-white md:p-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-white md:text-3xl">
          Where are you forming your LLC?
        </h1>
        <p className="max-w-2xl text-slate-400">
          Choose the state where you want to register. Filing fees shown are
          typical state filing charges (subject to change).
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {POPULAR_STATES.map(({ code, name, feeCents }) => {
          const isSelected = data.stateCode === code;
          return (
            <button
              key={code}
              type="button"
              onClick={() => handleSelectState(code)}
              className="group block h-full w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            >
              <Card
                className={cn(
                  "h-full border-slate-700 bg-slate-800/40 transition-colors",
                  "group-hover:border-teal-500/40 group-hover:bg-slate-800/70",
                  isSelected &&
                    "border-teal-500/60 ring-2 ring-teal-400/50 ring-offset-2 ring-offset-slate-900"
                )}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-lg font-semibold text-white">
                      {name}
                    </CardTitle>
                    <span className="shrink-0 rounded-md bg-slate-900/80 px-2 py-0.5 font-mono text-xs font-medium text-teal-300">
                      {code}
                    </span>
                  </div>
                  <CardDescription className="text-slate-400">
                    State filing fee
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="font-mono text-xl font-semibold text-teal-300">
                    {formatFilingFee(feeCents)}
                  </p>
                </CardContent>
              </Card>
            </button>
          );
        })}
      </div>
    </div>
  );
}
