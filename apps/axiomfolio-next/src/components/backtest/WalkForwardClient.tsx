"use client";

import React, { useState } from 'react';
import Link from 'next/link';
import { ListChecks, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { ChartGlassCard } from '@/components/ui/ChartGlassCard';

import StudyForm from '@/components/backtest/StudyForm';
import StudyResults from '@/components/backtest/StudyResults';

import {
  useWalkForwardStudies,
  useWalkForwardStudy,
} from '@/hooks/useWalkForwardStudies';
import useEntitlement from '@/hooks/useEntitlement';

/**
 * /backtest/walk-forward — landing for the walk-forward optimizer.
 *
 * Layout:
 *   [Form pane]   [Results pane]
 *   [Past studies list]
 *
 * Selecting a row in the past-studies list swaps the results pane to that
 * study; creating a new study auto-selects it so the user immediately sees
 * "running" → live progress → completed without an extra click.
 */

const FEATURE_KEY = 'research.walk_forward_optimizer';

const WalkForwardClient: React.FC = () => {
  const ent = useEntitlement();
  const [selected, setSelected] = useState<number | null>(null);

  const list = useWalkForwardStudies();
  const detail = useWalkForwardStudy(selected);

  if (ent.isLoading) {
    return (
      <div className="grid min-h-[40vh] place-content-center text-sm text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }

  if (!ent.can(FEATURE_KEY)) {
    const minTier = ent.requireTier(FEATURE_KEY);
    return (
      <ChartGlassCard
        as="section"
        ariaLabel="Walk-forward optimizer locked"
        padding="lg"
        className="mx-auto mt-12 max-w-xl text-center"
      >
        <h1 className="text-xl font-semibold">Walk-forward optimizer</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          This research tool is available on the {minTier ?? 'Pro'} tier and
          above. Upgrade to run Optuna-driven hyperparameter studies with
          per-regime attribution.
        </p>
        <div className="mt-6">
          <Button asChild>
            <Link href="/pricing">View pricing</Link>
          </Button>
        </div>
      </ChartGlassCard>
    );
  }

  return (
    <div className="space-y-6 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold">Walk-forward optimizer</h1>
        <p className="text-sm text-muted-foreground">
          Search a parameter space against your historical universe; score by
          out-of-sample windows; attribute by market regime.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(360px,420px)_1fr]">
        <StudyForm onCreated={setSelected} />

        <div className="space-y-6">
          {selected === null ? (
            <ChartGlassCard
              as="section"
              ariaLabel="No study selected"
              padding="md"
              className="grid h-56 place-content-center text-center"
            >
              <p className="text-sm text-muted-foreground">
                Run a new study or pick one from the list below to see results here.
              </p>
            </ChartGlassCard>
          ) : detail.isLoading ? (
            <ChartGlassCard
              as="section"
              ariaLabel="Loading study"
              padding="md"
              className="grid h-56 place-content-center"
            >
              <Loader2 className="size-5 animate-spin text-muted-foreground" />
            </ChartGlassCard>
          ) : detail.isError || !detail.data ? (
            <ChartGlassCard
              as="section"
              ariaLabel="Failed to load study"
              padding="md"
              className="grid h-56 place-content-center text-center"
            >
              <p className="text-sm text-muted-foreground">
                Failed to load study. {' '}
                <button
                  type="button"
                  className="underline"
                  onClick={() => detail.refetch()}
                >
                  Retry
                </button>
              </p>
            </ChartGlassCard>
          ) : (
            <StudyResults study={detail.data} />
          )}
        </div>
      </div>

      <ChartGlassCard
        as="section"
        ariaLabel="Past studies"
        padding="md"
      >
        <header className="mb-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ListChecks className="size-4 text-muted-foreground" />
            <h2 className="text-base font-semibold">Past studies</h2>
          </div>
          <span className="text-xs text-muted-foreground">
            {list.data?.length ?? 0} total
          </span>
        </header>

        {list.isLoading ? (
          <div className="grid h-24 place-content-center">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        ) : list.isError ? (
          <div className="text-sm text-muted-foreground">
            Failed to load studies. {' '}
            <button
              type="button"
              className="underline"
              onClick={() => list.refetch()}
            >
              Retry
            </button>
          </div>
        ) : !list.data || list.data.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            No studies yet — run your first one above.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-2 py-2 font-medium">Name</th>
                  <th className="px-2 py-2 font-medium">Strategy</th>
                  <th className="px-2 py-2 font-medium">Status</th>
                  <th className="px-2 py-2 font-medium">Trials</th>
                  <th className="px-2 py-2 font-medium">Best score</th>
                  <th className="px-2 py-2 font-medium">Created</th>
                  <th className="px-2 py-2" />
                </tr>
              </thead>
              <tbody>
                {list.data.map((s) => {
                  const isSelected = s.id === selected;
                  return (
                    <tr
                      key={s.id}
                      className={
                        isSelected
                          ? 'bg-muted/40'
                          : 'hover:bg-muted/20 transition-colors'
                      }
                    >
                      <td className="truncate px-2 py-2 font-medium">{s.name}</td>
                      <td className="px-2 py-2 text-xs text-muted-foreground">
                        {s.strategy_class}
                      </td>
                      <td className="px-2 py-2 text-xs">{s.status}</td>
                      <td className="px-2 py-2 font-mono text-xs">
                        {s.total_trials} / {s.n_trials}
                      </td>
                      <td className="px-2 py-2 font-mono text-xs">
                        {s.best_score === null
                          ? '—'
                          : s.best_score.toFixed(3)}
                      </td>
                      <td className="px-2 py-2 text-xs text-muted-foreground">
                        {s.created_at
                          ? new Date(s.created_at).toLocaleDateString()
                          : '—'}
                      </td>
                      <td className="px-2 py-2 text-right">
                        <Button
                          size="sm"
                          variant={isSelected ? 'default' : 'outline'}
                          onClick={() => setSelected(s.id)}
                        >
                          {isSelected ? 'Viewing' : 'View'}
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </ChartGlassCard>
    </div>
  );
};

export default WalkForwardClient;
