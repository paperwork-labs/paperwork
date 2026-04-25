/**
 * MonteCarlo page
 * ===============
 *
 * /backtest/monte-carlo — Pro+ tier-gated. Lets the user paste a list
 * of historical trade returns (or in a future iteration, load them
 * from a saved backtest study) and renders the resulting equity-curve
 * fan chart plus a summary of drawdown / Sharpe / probability stats.
 *
 * Iron-law compliance:
 * - Four explicit states (loading / error / empty / data) per the
 *   no-silent-fallback rule.
 * - Decimals-as-strings preserved through the API → service → page;
 *   we only coerce to number at the chart layer.
 * - TierGate handles the locked-state UI; backend enforces the
 *   actual data contract via require_feature.
 */
"use client";

import * as React from 'react';
import axios from 'axios';
import { Loader2, Play, Sparkles } from 'lucide-react';

import { Page, PageHeader } from '@/components/ui/Page';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import TierGate from '@/components/billing/TierGate';

import { MonteCarloChart } from '@/components/backtest/MonteCarloChart';
import { useMonteCarlo } from '@/hooks/useMonteCarlo';
import {
  decimalToNumber,
  formatProbability,
  type MonteCarloResult,
} from '@/services/backtest';

// Default seed sample — a small "looks like a real swing strategy" set
// so the page is interactive on first load. Users replace this with
// their own returns. Returns are parsed as ``decimal fractions`` so
// 0.025 means +2.5%. Length matches backend ``MIN_SAMPLES`` (30).
const _BASE_DEFAULT_RETURNS = [
  '0.020',
  '-0.010',
  '0.035',
  '-0.025',
  '0.045',
  '-0.015',
  '0.025',
  '-0.020',
  '0.030',
  '-0.005',
  '0.015',
  '-0.030',
  '0.040',
  '-0.020',
  '0.010',
] as const;
const DEFAULT_RETURNS = [..._BASE_DEFAULT_RETURNS, ..._BASE_DEFAULT_RETURNS].join('\n');

/* -------------------------------------------------------------------------
 * Pure parsing helper (exported indirectly for testability — tests
 * import via the page module).
 * ---------------------------------------------------------------------- */
const MIN_MONTE_CARLO_TRADES = 30;

function parseReturns(input: string): { values: string[]; error?: string } {
  const tokens = input
    .split(/[\s,;]+/)
    .map((t) => t.trim())
    .filter(Boolean);
  if (tokens.length === 0) {
    return { values: [], error: 'Enter at least one trade return.' };
  }
  if (tokens.length < MIN_MONTE_CARLO_TRADES) {
    return {
      values: [],
      error: `Enter at least ${MIN_MONTE_CARLO_TRADES} trade returns (required for a stable bootstrap).`,
    };
  }
  for (const t of tokens) {
    const n = Number(t);
    if (!Number.isFinite(n)) {
      return {
        values: [],
        error: `"${t}" is not a valid number — use decimal fractions like 0.025 for 2.5%.`,
      };
    }
    if (Math.abs(n) > 1) {
      return {
        values: [],
        error: `"${t}" looks like a percentage, but returns must be entered as decimal fractions (for example, 0.025 for 2.5%).`,
      };
    }
  }
  return { values: tokens };
}

function monteCarloMutationErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { detail?: unknown } | undefined;
    if (data?.detail != null) {
      const d = data.detail;
      return typeof d === 'string' ? d : JSON.stringify(d);
    }
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return 'The Monte Carlo endpoint returned an error. Verify your inputs and try again.';
}

interface SummaryGridProps {
  result: MonteCarloResult;
}

function SummaryGrid({ result }: SummaryGridProps) {
  const cells: Array<{ label: string; value: string; hint?: string }> = [
    {
      label: 'Median terminal',
      value: `$${decimalToNumber(result.terminal_value.median).toLocaleString(
        undefined,
        { maximumFractionDigits: 0 },
      )}`,
      hint: 'P50 final equity across simulations',
    },
    {
      label: '5th–95th terminal',
      value: `$${decimalToNumber(result.terminal_value.p5).toLocaleString(
        undefined,
        { maximumFractionDigits: 0 },
      )} – $${decimalToNumber(result.terminal_value.p95).toLocaleString(
        undefined,
        { maximumFractionDigits: 0 },
      )}`,
      hint: '90% confidence interval on final equity',
    },
    {
      label: 'Median max drawdown',
      value: `${decimalToNumber(result.max_drawdown_pct.median).toFixed(1)}%`,
      hint: 'Typical worst peak-to-trough across sims',
    },
    {
      label: '95th-pct max drawdown',
      value: `${decimalToNumber(result.max_drawdown_pct.p95).toFixed(1)}%`,
      hint: 'Tail-risk drawdown (worse than 95% of sims)',
    },
    {
      label: 'Median Sharpe',
      value: decimalToNumber(result.sharpe.median).toFixed(2),
      hint: 'Annualized, sqrt(252) scaling',
    },
    {
      label: 'Probability of loss',
      value: formatProbability(result.probability_of_loss),
      hint: 'P(terminal < initial capital)',
    },
    {
      label: 'Probability of 2x',
      value: formatProbability(result.probability_of_2x),
      hint: 'P(terminal ≥ 2 × initial capital)',
    },
    {
      label: 'Sample size',
      value: `${result.params.n_simulations.toLocaleString()} sims · ${result.params.n_trades} trades`,
    },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {cells.map((c) => (
        <Card key={c.label} size="sm">
          <CardContent className="space-y-0.5 pt-4">
            <p className="text-xs text-muted-foreground">{c.label}</p>
            <p className="text-lg font-semibold tabular-nums text-foreground">
              {c.value}
            </p>
            {c.hint ? (
              <p className="text-[11px] text-muted-foreground">{c.hint}</p>
            ) : null}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function MonteCarloInner() {
  const [returnsText, setReturnsText] = React.useState(DEFAULT_RETURNS);
  const [nSimulations, setNSimulations] = React.useState('10000');
  const [initialCapital, setInitialCapital] = React.useState('100000');
  const [seedText, setSeedText] = React.useState('');

  const mutation = useMonteCarlo();

  const handleRun = React.useCallback(() => {
    const parsed = parseReturns(returnsText);
    if (parsed.error) {
      // Surface as a controlled error rather than throwing -- TanStack
      // Query won't see this branch; we set it via mutate's onError-style
      // fallback by passing a malformed payload would be wrong. Instead,
      // bail and rely on the inline message below.
      mutation.reset();
      // Emulate an error in local state by toggling a custom field --
      // simplest path is to call mutate with a known-bad value so the
      // backend returns 400 (which it will, see _validate_inputs).
      // Even simpler: just don't run.
      return;
    }
    const seedParsed = seedText.trim() === '' ? null : Number(seedText);
    mutation.mutate({
      trade_returns: parsed.values,
      n_simulations: Number(nSimulations),
      initial_capital: initialCapital,
      seed: seedParsed,
      run_all_scenarios: false,
    });
  }, [returnsText, nSimulations, initialCapital, seedText, mutation]);

  const parseInline = parseReturns(returnsText);
  const result =
    mutation.data?.mode === 'single' ? mutation.data.result : undefined;

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardContent className="grid gap-4 pt-6 lg:grid-cols-[1fr_220px]">
          <div className="space-y-2">
            <Label htmlFor="returns">Trade returns</Label>
            <Textarea
              id="returns"
              value={returnsText}
              onChange={(e) => setReturnsText(e.target.value)}
              rows={8}
              className="font-mono text-xs"
              placeholder="One return per line, e.g. 0.025 for +2.5%"
              spellCheck={false}
            />
            {parseInline.error ? (
              <p className="text-xs text-destructive">{parseInline.error}</p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Parsed {parseInline.values.length} trades. Decimal fractions
                only (0.025 = +2.5%).
              </p>
            )}
          </div>
          <div className="flex flex-col gap-3">
            <div className="space-y-1">
              <Label htmlFor="n_sims">Simulations</Label>
              <Input
                id="n_sims"
                type="number"
                min={100}
                max={100000}
                step={100}
                value={nSimulations}
                onChange={(e) => setNSimulations(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="initial">Initial capital</Label>
              <Input
                id="initial"
                type="number"
                min={1}
                value={initialCapital}
                onChange={(e) => setInitialCapital(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="seed">Seed (optional)</Label>
              <Input
                id="seed"
                type="number"
                value={seedText}
                onChange={(e) => setSeedText(e.target.value)}
                placeholder="Reproducibility"
              />
            </div>
            <Button
              type="button"
              onClick={handleRun}
              disabled={mutation.isPending || !!parseInline.error}
              className="mt-1"
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Running…
                </>
              ) : (
                <>
                  <Play className="mr-2 size-4" />
                  Run simulation
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Four explicit states — no silent fallback. */}
      {mutation.isPending ? (
        <Card>
          <CardContent className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Resampling {Number(nSimulations).toLocaleString()} bootstrap
            iterations…
          </CardContent>
        </Card>
      ) : mutation.isError ? (
        <Card className="border-destructive/40">
          <CardContent className="space-y-2 py-6 text-sm">
            <p className="font-medium text-destructive">Simulation failed</p>
            <p className="text-muted-foreground">
              {monteCarloMutationErrorMessage(mutation.error)}
            </p>
          </CardContent>
        </Card>
      ) : result ? (
        <div className="flex flex-col gap-4">
          <SummaryGrid result={result} />
          <MonteCarloChart equityCurve={result.equity_curve} />
        </div>
      ) : (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center gap-2 py-12 text-center text-sm text-muted-foreground">
            <Sparkles className="size-5" />
            <p>
              Configure inputs and click <strong>Run simulation</strong> to
              generate a confidence band.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function MonteCarloPage() {
  return (
    <Page>
      <PageHeader
        title="Monte Carlo simulator"
        subtitle="Bootstrap-resample backtest trade returns to estimate confidence intervals on equity curve, drawdown, and Sharpe."
      />
      <TierGate
        feature="research.monte_carlo"
        costJustification="Monte Carlo runs are CPU-bound and bundled with the Pro+ research kit."
      >
        <MonteCarloInner />
      </TierGate>
    </Page>
  );
}
