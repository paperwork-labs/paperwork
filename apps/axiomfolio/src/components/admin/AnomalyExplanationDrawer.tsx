/**
 * AnomalyExplanationDrawer — admin-only side panel that renders one
 * AutoOps anomaly explanation in detail.
 *
 * The drawer has two entry modes:
 *   1. `"dimension"` mode — the operator clicked "Explain" on a
 *      composite-health dimension card. The drawer POSTs to
 *      `/api/v1/admin/agent/explain/dimension` and renders the response.
 *   2. `"existing"` mode — the operator clicked "Open" on a row in the
 *      Recent Explanations panel. The explanation is already in hand, so
 *      we render it without an extra round-trip.
 *
 * Loading / error / empty / data states are kept distinct (no silent
 * fallbacks per `.cursor/rules/no-silent-fallback.mdc`). Slide animation
 * gracefully degrades for users with `prefers-reduced-motion`.
 */
import * as React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { useMutation } from '@tanstack/react-query';
import { ExternalLink, Info, Sparkles, X } from 'lucide-react';

import { AgentMarkdown } from '@/components/agent/AgentMarkdown';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/skeleton';
import { useBackendUser } from '@/hooks/use-backend-user';
import { cn } from '@/lib/utils';
import {
  explainDimension,
  type AutoOpsExplanation,
  type AutoOpsRemediationStep,
} from '@/services/autoOps';
import { isPlatformAdminRole } from '@/utils/userRole';

const RUNBOOK_BASE_URL =
  'https://github.com/sankalp404/axiomfolio/blob/main/docs/MARKET_DATA_RUNBOOK.md';

function runbookHref(section: string | null | undefined): string | null {
  if (!section) return null;
  const trimmed = section.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith('#')) return `${RUNBOOK_BASE_URL}${trimmed}`;
  const hashIdx = trimmed.indexOf('#');
  if (hashIdx === -1) return null;
  return `${RUNBOOK_BASE_URL}${trimmed.slice(hashIdx)}`;
}

export interface DimensionTrigger {
  mode: 'dimension';
  dimension: string;
  dimensionPayload: Record<string, unknown>;
}

export interface ExistingTrigger {
  mode: 'existing';
  explanation: AutoOpsExplanation;
}

export type AnomalyExplanationTrigger = DimensionTrigger | ExistingTrigger;

export interface AnomalyExplanationDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** What to render when the drawer opens. `null` keeps the drawer closed. */
  trigger: AnomalyExplanationTrigger | null;
}

function StepRow({ step }: { step: AutoOpsRemediationStep }) {
  const href = runbookHref(step.runbook_section);
  return (
    <li className="flex gap-3" data-testid="explanation-step">
      <span
        aria-hidden
        className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full border border-border bg-muted/40 text-[11px] font-semibold tabular-nums text-foreground"
      >
        {step.order}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm leading-relaxed text-foreground">{step.description}</p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          {href ? (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
              data-testid="step-runbook-link"
            >
              {step.runbook_section}
              <ExternalLink className="size-3" aria-hidden />
            </a>
          ) : step.runbook_section ? (
            <span className="text-muted-foreground/70">{step.runbook_section}</span>
          ) : null}
          {step.proposed_task ? (
            <code className="rounded border border-border bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              {step.proposed_task}
            </code>
          ) : null}
          {step.requires_approval ? (
            <Badge
              variant="outline"
              className="border-amber-500/40 text-[10px] text-amber-700 dark:text-amber-300"
            >
              Approval required
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="border-emerald-500/40 text-[10px] text-emerald-700 dark:text-emerald-300"
            >
              Read-only
            </Badge>
          )}
        </div>
        {step.rationale ? (
          <p className="mt-1 text-[11px] italic text-muted-foreground/80">{step.rationale}</p>
        ) : null}
      </div>
    </li>
  );
}

function DegradedBadge() {
  return (
    <Badge
      variant="outline"
      className="gap-1 border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300"
      data-testid="degraded-badge"
      title="The LLM provider was unavailable; this explanation uses the deterministic fallback runbook."
    >
      <Info className="size-3" aria-hidden />
      Degraded
    </Badge>
  );
}

function DrawerSkeleton() {
  return (
    <div className="space-y-4 p-5" data-testid="drawer-skeleton">
      <Skeleton className="h-5 w-2/3" />
      <Skeleton className="h-3 w-1/3" />
      <Skeleton className="h-24 w-full" />
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex gap-3">
            <Skeleton className="size-6 shrink-0 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

interface DrawerBodyProps {
  explanation: AutoOpsExplanation;
}

function DrawerBody({ explanation }: DrawerBodyProps) {
  const payload = explanation.payload ?? {};
  const narrative = (payload.narrative ?? explanation.summary ?? '').trim();
  const steps = (payload.steps ?? []).slice().sort((a, b) => a.order - b.order);
  const generatedAt = explanation.generated_at
    ? new Date(explanation.generated_at).toLocaleString()
    : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto" data-testid="drawer-body">
      <div className="space-y-1 border-b border-border px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
            {explanation.category}
          </Badge>
          <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
            {explanation.severity}
          </Badge>
          {explanation.is_fallback ? <DegradedBadge /> : null}
        </div>
        <h2 className="font-heading text-base font-semibold leading-snug text-foreground">
          {explanation.title}
        </h2>
        {explanation.summary ? (
          <p className="text-sm text-muted-foreground">{explanation.summary}</p>
        ) : null}
        <p className="text-[10px] text-muted-foreground/70">
          {explanation.model}
          {generatedAt ? ` · ${generatedAt}` : ''}
          {explanation.confidence ? ` · confidence ${explanation.confidence}` : ''}
        </p>
      </div>

      {narrative ? (
        <section className="space-y-2 border-b border-border px-5 py-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Narrative
          </p>
          <AgentMarkdown content={narrative} />
        </section>
      ) : null}

      {payload.root_cause_hypothesis ? (
        <section className="space-y-2 border-b border-border px-5 py-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Root cause hypothesis
          </p>
          <p className="text-sm text-foreground">{payload.root_cause_hypothesis}</p>
        </section>
      ) : null}

      <section className="space-y-3 border-b border-border px-5 py-4">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Remediation steps
        </p>
        {steps.length > 0 ? (
          <ol className="space-y-3">
            {steps.map((step) => (
              <StepRow key={step.order} step={step} />
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">
            No remediation steps were produced for this anomaly.
          </p>
        )}
      </section>

      {(payload.runbook_excerpts?.length ?? 0) > 0 ? (
        <section className="space-y-2 px-5 py-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Runbook references
          </p>
          <ul className="space-y-1">
            {payload.runbook_excerpts!.map((excerpt) => {
              const href = runbookHref(excerpt);
              return (
                <li key={excerpt} className="text-xs text-muted-foreground">
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
                    >
                      {excerpt}
                      <ExternalLink className="size-3" aria-hidden />
                    </a>
                  ) : (
                    excerpt
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

export function AnomalyExplanationDrawer({
  open,
  onOpenChange,
  trigger,
}: AnomalyExplanationDrawerProps) {
  const { user } = useBackendUser();
  const isAdmin = isPlatformAdminRole(user?.role);

  const mutation = useMutation({
    mutationFn: explainDimension,
  });
  // Capture mutation primitives in refs so the effect below depends on
  // exactly what the operator did (open / trigger), not on the
  // (unstable) mutation object identity. Including `mutation` directly
  // in the dep array makes React Hooks happy but re-fires the request
  // every time the mutation transitions state.
  const mutateRef = React.useRef(mutation.mutate);
  mutateRef.current = mutation.mutate;
  const resetRef = React.useRef(mutation.reset);
  resetRef.current = mutation.reset;

  React.useEffect(() => {
    if (!open) {
      resetRef.current();
      return;
    }
    if (trigger?.mode !== 'dimension') return;
    mutateRef.current({
      dimension: trigger.dimension,
      dimensionPayload: trigger.dimensionPayload,
    });
  }, [open, trigger]);

  if (!isAdmin) return null;

  const inExistingMode = trigger?.mode === 'existing';
  const existing = inExistingMode ? trigger.explanation : null;
  const fetched = mutation.data ?? null;
  const explanation: AutoOpsExplanation | null = existing ?? fetched;

  // In dimension mode the very first render happens *before* the
  // request-firing effect commits, so `mutation.isPending` is still
  // false at that point. Treat any non-settled state (`idle` or
  // `pending`) as loading so the operator sees a skeleton immediately
  // instead of an empty drawer flash.
  const isLoading =
    trigger?.mode === 'dimension' &&
    (mutation.status === 'idle' || mutation.status === 'pending');
  const isError = trigger?.mode === 'dimension' && mutation.isError;
  const errorMessage = (() => {
    if (!isError) return null;
    const e = mutation.error as
      | { response?: { data?: { detail?: string } }; message?: string }
      | undefined;
    return (
      e?.response?.data?.detail ||
      e?.message ||
      'AutoOps could not generate an explanation for this dimension.'
    );
  })();

  const headerTitle = (() => {
    if (existing) return 'Anomaly Explanation';
    if (trigger?.mode === 'dimension') return `Explain: ${trigger.dimension}`;
    return 'Anomaly Explanation';
  })();

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            'fixed inset-0 z-50 bg-black/40',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0',
            'motion-reduce:animate-none motion-reduce:transition-none',
          )}
        />
        <Dialog.Content
          data-testid="anomaly-explanation-drawer"
          className={cn(
            'fixed top-0 right-0 z-50 flex h-[100dvh] w-[95vw] max-w-[560px] flex-col',
            'border-l border-border bg-card text-card-foreground shadow-xl outline-none',
            'data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right',
            'data-[state=open]:animate-in data-[state=open]:slide-in-from-right',
            'duration-200 motion-reduce:animate-none motion-reduce:duration-0',
          )}
          aria-describedby={undefined}
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <div className="flex min-w-0 items-center gap-2">
              <Sparkles className="size-4 shrink-0 text-primary" aria-hidden />
              <Dialog.Title className="font-heading truncate text-sm font-medium">
                {headerTitle}
              </Dialog.Title>
            </div>
            <Dialog.Close asChild>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label="Close"
              >
                <X className="size-4" aria-hidden />
              </Button>
            </Dialog.Close>
          </div>

          {isLoading ? (
            <DrawerSkeleton />
          ) : isError ? (
            <div className="flex flex-1 items-center justify-center p-5">
              <ErrorState
                title="Couldn't generate explanation"
                description={errorMessage ?? undefined}
                error={mutation.error}
                retry={
                  trigger?.mode === 'dimension'
                    ? () =>
                        mutation.mutate({
                          dimension: trigger.dimension,
                          dimensionPayload: trigger.dimensionPayload,
                        })
                    : undefined
                }
              />
            </div>
          ) : explanation ? (
            <DrawerBody explanation={explanation} />
          ) : (
            <div className="flex flex-1 items-center justify-center p-5 text-sm text-muted-foreground">
              No explanation selected.
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default AnomalyExplanationDrawer;
