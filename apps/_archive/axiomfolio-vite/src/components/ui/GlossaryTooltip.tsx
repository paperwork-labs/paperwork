import { ReactNode } from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import glossaryData from '@/data/glossary.json';

type GlossaryCategory = keyof typeof glossaryData;

interface GlossaryTooltipProps {
  term: string;
  category?: GlossaryCategory;
  children: ReactNode;
  side?: 'top' | 'bottom' | 'left' | 'right';
}

function findTerm(term: string, category?: GlossaryCategory) {
  const termLower = term.toLowerCase().replace(/[^a-z0-9_]/g, '_');

  if (category && glossaryData[category]) {
    const categoryData = glossaryData[category] as Record<string, unknown>;
    if (categoryData[termLower]) {
      return categoryData[termLower] as { term: string; short: string; definition: string };
    }
  }

  for (const cat of Object.values(glossaryData)) {
    const catData = cat as Record<string, unknown>;
    if (catData[termLower]) {
      return catData[termLower] as { term: string; short: string; definition: string };
    }
  }

  return null;
}

export function GlossaryTooltip({
  term,
  category,
  children,
  side = 'top',
}: GlossaryTooltipProps) {
  const entry = findTerm(term, category);

  if (!entry) {
    return <>{children}</>;
  }

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="cursor-help border-b border-dashed border-muted-foreground/50">
            {children}
          </span>
        </TooltipTrigger>
        <TooltipContent side={side} className="max-w-xs">
          <div className="space-y-1">
            <p className="font-semibold text-sm">{entry.term}</p>
            <p className="text-xs text-muted-foreground">{entry.definition}</p>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export { glossaryData };
