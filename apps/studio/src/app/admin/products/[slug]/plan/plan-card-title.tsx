"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { cn } from "@paperwork-labs/ui";

type PlanCardTitleProps = {
  title: string;
};

export function PlanCardTitle({ title }: PlanCardTitleProps) {
  const [expanded, setExpanded] = useState(false);
  const needsToggle = title.length > 180 || title.split(/\s+/).length > 28;

  return (
    <div className="min-w-0">
      <h2
        className={cn(
          "text-lg font-semibold tracking-tight text-zinc-100 break-words",
          needsToggle && !expanded && "line-clamp-3",
        )}
      >
        {title}
      </h2>
      {needsToggle ? (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-medium text-[var(--status-info)] hover:text-[rgb(186_230_253)]"
          aria-expanded={expanded}
        >
          {expanded ? (
            <>
              Show less <ChevronUp className="h-3 w-3" aria-hidden />
            </>
          ) : (
            <>
              Show full title <ChevronDown className="h-3 w-3" aria-hidden />
            </>
          )}
        </button>
      ) : null}
    </div>
  );
}
