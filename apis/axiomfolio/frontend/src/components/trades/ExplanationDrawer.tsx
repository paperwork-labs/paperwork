import * as React from 'react';
import { Loader2, RefreshCw, AlertTriangle } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  useRegenerateTradeDecisionExplanation,
  useTradeDecisionExplanation,
} from '@/hooks/useTradeDecisionExplanation';
import type {
  TradeDecisionExplanation,
  TradeDecisionTrigger,
} from '@/types/tradeDecision';

export interface ExplanationDrawerProps {
  orderId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const TRIGGER_LABEL: Record<TradeDecisionTrigger, string> = {
  pick: 'Validated pick',
  scan: 'Scanner signal',
  rebalance: 'Rebalance',
  manual: 'Manual',
  strategy: 'Strategy',
  unknown: 'Unknown',
};

const TRIGGER_BADGE_CLASS: Record<TradeDecisionTrigger, string> = {
  pick: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
  scan: 'border-sky-500/40 bg-sky-500/10 text-sky-800 dark:text-sky-200',
  rebalance: 'border-primary/40 bg-primary/10',
  manual: 'border-border bg-muted/50 text-muted-foreground',
  strategy: 'border-violet-500/40 bg-violet-500/10 text-violet-800 dark:text-violet-200',
  unknown: 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100',
};

function StatusBadge({ trigger }: { trigger: TradeDecisionTrigger }) {
  return (
    <Badge variant="outline" className={cn('h-6', TRIGGER_BADGE_CLASS[trigger])}>
      {TRIGGER_LABEL[trigger]}
    </Badge>
  );
}

function RiskRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border border-border bg-muted/30 p-2">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className="text-xs">{value}</span>
    </div>
  );
}

function NarrativeBlock({ text }: { text: string }) {
  // We render the LLM narrative as plain whitespace-respecting paragraphs
  // rather than parsing markdown. The system prompt forbids headings /
  // bullets / emojis in the narrative field, so anything else would be
  // a contract violation worth surfacing as-is.
  const paragraphs = text.split(/\n\s*\n/).filter((p) => p.trim().length > 0);
  if (paragraphs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No narrative was returned.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3 text-sm leading-relaxed">
      {paragraphs.map((p, i) => (
        <p key={i} className="text-foreground">
          {p}
        </p>
      ))}
    </div>
  );
}

interface ExplanationBodyProps {
  data: TradeDecisionExplanation;
  isRegenerating: boolean;
  onRegenerate: () => void;
}

function ExplanationBody({ data, isRegenerating, onRegenerate }: ExplanationBodyProps) {
  const { payload } = data;
  return (
    <div data-testid="explanation-body" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge trigger={payload.trigger} />
        {data.is_fallback ? (
          <Badge
            variant="outline"
            className="h-6 border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100"
          >
            <AlertTriangle className="mr-1 size-3" aria-hidden />
            Degraded
          </Badge>
        ) : null}
        <span className="text-xs text-muted-foreground">
          v{data.version} · {data.model_used}
        </span>
        <div className="ml-auto">
          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={onRegenerate}
            disabled={isRegenerating}
            aria-busy={isRegenerating}
          >
            {isRegenerating ? (
              <Loader2 className="mr-1 size-3 animate-spin" aria-hidden />
            ) : (
              <RefreshCw className="mr-1 size-3" aria-hidden />
            )}
            Regenerate
          </Button>
        </div>
      </div>

      <div>
        <h3 className="text-base font-semibold text-foreground">
          {payload.headline}
        </h3>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Why this trade
        </span>
        <ul className="flex flex-col gap-1.5 pl-4">
          {payload.rationale_bullets.map((b, i) => (
            <li key={i} className="list-disc text-sm text-foreground">
              {b}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Risk context
        </span>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <RiskRow label="Position size" value={payload.risk_context.position_size_label} />
          <RiskRow label="Stop placement" value={payload.risk_context.stop_placement} />
          <RiskRow label="Regime alignment" value={payload.risk_context.regime_alignment} />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Outcome so far
        </span>
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/30 p-2 text-xs">
          <Badge variant="outline" className="h-5 capitalize">
            {payload.outcome_so_far.status}
          </Badge>
          {payload.outcome_so_far.pnl_label ? (
            <span className="font-mono text-xs">{payload.outcome_so_far.pnl_label}</span>
          ) : null}
          <span className="text-muted-foreground">{payload.outcome_so_far.summary}</span>
        </div>
      </div>

      <div className="flex flex-col gap-1.5 border-t border-border pt-3">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Narrative
        </span>
        <NarrativeBlock text={data.narrative || payload.narrative} />
      </div>
    </div>
  );
}

export function ExplanationDrawer({ orderId, open, onOpenChange }: ExplanationDrawerProps) {
  const enabled = open && orderId != null;
  const query = useTradeDecisionExplanation({ orderId, enabled });
  const regen = useRegenerateTradeDecisionExplanation(orderId);

  const handleRegenerate = React.useCallback(() => {
    if (orderId == null) return;
    regen.mutate();
  }, [orderId, regen]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl"
        data-testid="trade-decision-explanation-drawer"
      >
        <DialogHeader>
          <DialogTitle>Why this trade was placed</DialogTitle>
          <DialogDescription>
            Read-only explanation derived from the audit trail at order time.
          </DialogDescription>
        </DialogHeader>

        {orderId == null ? (
          <p className="text-sm text-muted-foreground">No order selected.</p>
        ) : query.isLoading ? (
          <div
            data-testid="explanation-loading"
            className="flex items-center gap-2 text-sm text-muted-foreground"
          >
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Generating explanation…
          </div>
        ) : query.isError ? (
          <div
            data-testid="explanation-error"
            className="flex flex-col gap-2 text-sm"
          >
            <p className="text-destructive">
              Could not load this explanation.
            </p>
            <Button
              type="button"
              size="xs"
              variant="outline"
              onClick={() => query.refetch()}
            >
              Retry
            </Button>
          </div>
        ) : query.data ? (
          <ExplanationBody
            data={query.data}
            isRegenerating={regen.isPending}
            onRegenerate={handleRegenerate}
          />
        ) : (
          <p className="text-sm text-muted-foreground">
            No explanation available.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default ExplanationDrawer;
