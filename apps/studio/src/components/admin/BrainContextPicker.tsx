"use client";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  cn,
} from "@paperwork-labs/ui";
import { Building2, Check, ChevronDown, Home, User } from "lucide-react";

import type { BrainOrganizationContext } from "@/lib/brain-context";
import { useBrainContext } from "@/lib/brain-context";

const OPTIONS: {
  id: BrainOrganizationContext;
  label: string;
  Icon: typeof User;
  ringClass: string;
}[] = [
  {
    id: "personal",
    label: "Personal",
    Icon: User,
    ringClass: "ring-sky-500/90",
  },
  {
    id: "paperwork-labs",
    label: "Paperwork Labs",
    Icon: Building2,
    ringClass: "ring-violet-500/90",
  },
  {
    id: "household",
    label: "Household",
    Icon: Home,
    ringClass: "ring-emerald-500/90",
  },
];

function OptionAvatar({
  id,
  size = "md",
}: {
  id: BrainOrganizationContext;
  size?: "sm" | "md";
}) {
  const meta = OPTIONS.find((o) => o.id === id)!;
  const Icon = meta.Icon;
  const dim = size === "sm" ? "h-7 w-7" : "h-9 w-9";
  const iconDim = size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4";
  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-zinc-800 ring-2 ring-offset-2 ring-offset-zinc-950",
        dim,
        meta.ringClass,
      )}
      aria-hidden
    >
      <Icon className={cn(iconDim, "text-zinc-200")} />
    </span>
  );
}

export function BrainContextPicker() {
  const { context, setContext } = useBrainContext();
  const current = OPTIONS.find((o) => o.id === context)!;

  return (
    <div className="flex items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            data-testid="brain-context-picker-trigger"
            aria-label={`Brain workspace context: ${current.label}. Open menu to switch.`}
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-700/80 bg-zinc-900/60 px-2 py-1.5 text-left text-xs text-zinc-200 transition hover:border-zinc-600 hover:bg-zinc-800/70"
          >
            <OptionAvatar id={context} size="sm" />
            <span className="hidden max-w-[10rem] truncate font-medium sm:inline">
              {current.label}
            </span>
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-zinc-500" aria-hidden />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="min-w-[13.5rem] border-zinc-700 bg-zinc-900 text-zinc-100"
        >
          <DropdownMenuLabel className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
            Brain context
          </DropdownMenuLabel>
          <DropdownMenuSeparator className="bg-zinc-800" />
          {OPTIONS.map((opt) => {
            const selected = context === opt.id;
            return (
              <DropdownMenuItem
                key={opt.id}
                data-testid={`brain-context-option-${opt.id}`}
                className={cn(
                  "cursor-pointer gap-3 py-2.5 focus:bg-zinc-800 focus:text-zinc-50",
                  selected && "bg-zinc-800/80",
                )}
                onSelect={(e) => {
                  e.preventDefault();
                  setContext(opt.id);
                }}
              >
                <OptionAvatar id={opt.id} />
                <span className="flex-1 font-medium">{opt.label}</span>
                {selected ? (
                  <Check className="h-4 w-4 shrink-0 text-emerald-400" aria-hidden />
                ) : (
                  <span className="inline-block h-4 w-4 shrink-0" aria-hidden />
                )}
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuContent>
      </DropdownMenu>
      <span
        data-testid="brain-context-badge"
        className="hidden rounded-full border border-zinc-700/80 bg-zinc-900/80 px-2 py-1 text-[11px] font-medium tabular-nums text-zinc-400 md:inline-flex md:items-center"
        title={`Active Brain context: ${current.label}`}
      >
        {current.label}
      </span>
    </div>
  );
}
