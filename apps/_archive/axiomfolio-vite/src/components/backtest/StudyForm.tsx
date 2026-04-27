import React, { useMemo, useState } from 'react';
import toast from 'react-hot-toast';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ChartGlassCard } from '@/components/ui/ChartGlassCard';

import {
  useCreateWalkForwardStudy,
  useStrategyOptions,
} from '@/hooks/useWalkForwardStudies';
import type {
  CreateStudyPayload,
  ParamSpace,
  RegimeFilter,
} from '@/services/backtest';

/**
 * StudyForm — collect inputs for a new walk-forward study.
 *
 * The param-space text area is intentionally low-friction (raw JSON) so a
 * power user can paste a saved spec without us having to ship a builder UI
 * yet. We validate JSON shape client-side so the API never sees malformed
 * payloads, and we surface backend validation errors verbatim because they
 * carry the precise reason a study was rejected.
 */

interface StudyFormProps {
  onCreated: (id: number) => void;
}

const DEFAULT_PARAM_SPACE = `{
  "rsi_max":        { "type": "int",   "low": 60,  "high": 80,  "step": 5 },
  "vol_ratio_min":  { "type": "float", "low": 1.1, "high": 2.5 },
  "stop_atr_mult":  { "type": "float", "low": 1.5, "high": 3.0 }
}`;

const REGIMES: RegimeFilter[] = [null, 'R1', 'R2', 'R3', 'R4', 'R5'];

function parseSymbols(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
}

function todayMinus(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

const StudyForm: React.FC<StudyFormProps> = ({ onCreated }) => {
  const opts = useStrategyOptions();
  const create = useCreateWalkForwardStudy();

  const [name, setName] = useState('Stage-2 breakout sweep');
  const [strategy, setStrategy] = useState('');
  const [objective, setObjective] = useState('sharpe_ratio');
  const [symbolsRaw, setSymbolsRaw] = useState('AAPL, MSFT, NVDA');
  const [datasetStart, setDatasetStart] = useState(todayMinus(730));
  const [datasetEnd, setDatasetEnd] = useState(todayMinus(1));
  const [trainDays, setTrainDays] = useState(180);
  const [testDays, setTestDays] = useState(45);
  const [nSplits, setNSplits] = useState(5);
  const [nTrials, setNTrials] = useState(50);
  const [regime, setRegime] = useState<RegimeFilter>(null);
  const [paramSpaceText, setParamSpaceText] = useState(DEFAULT_PARAM_SPACE);

  // Defaults for strategy/objective once the option list arrives.
  React.useEffect(() => {
    if (opts.data) {
      if (!strategy && opts.data.strategies.length > 0) {
        setStrategy(opts.data.strategies[0]);
      }
    }
  }, [opts.data, strategy]);

  const symbols = useMemo(() => parseSymbols(symbolsRaw), [symbolsRaw]);

  const isPending = create.isPending;
  const submitDisabled =
    isPending ||
    opts.isLoading ||
    !strategy ||
    symbols.length === 0 ||
    !datasetStart ||
    !datasetEnd;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    let parsedParamSpace: ParamSpace;
    try {
      parsedParamSpace = JSON.parse(paramSpaceText);
    } catch (err) {
      toast.error('Param space is not valid JSON');
      return;
    }

    const payload: CreateStudyPayload = {
      name: name.trim(),
      strategy_class: strategy,
      objective,
      param_space: parsedParamSpace,
      symbols,
      dataset_start: datasetStart,
      dataset_end: datasetEnd,
      train_window_days: Number(trainDays),
      test_window_days: Number(testDays),
      n_splits: Number(nSplits),
      n_trials: Number(nTrials),
      regime_filter: regime,
    };

    create.mutate(payload, {
      onSuccess: (study) => {
        toast.success(`Study "${study.name}" enqueued`);
        onCreated(study.id);
      },
      onError: (err: unknown) => {
        // axios error shape — surface the server's `detail` so users see the
        // actual reason (bad symbols, bad windows, tier gate, etc.).
        const detail =
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? 'Failed to create study';
        toast.error(detail);
      },
    });
  };

  return (
    <ChartGlassCard
      as="section"
      ariaLabel="Create walk-forward study"
      padding="md"
      className="w-full"
    >
      <header className="mb-4 flex items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold">New study</h2>
          <p className="text-sm text-muted-foreground">
            Optuna search over a parameter space, scored on rolling out-of-sample windows.
          </p>
        </div>
      </header>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <Label htmlFor="wf-name">Name</Label>
          <Input
            id="wf-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Stage-2 breakout sweep — Q1"
            required
          />
        </div>

        <div>
          <Label htmlFor="wf-strategy">Strategy</Label>
          <select
            id="wf-strategy"
            className="h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            disabled={opts.isLoading}
          >
            {!strategy ? <option value="">Select…</option> : null}
            {(opts.data?.strategies ?? []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div>
          <Label htmlFor="wf-objective">Objective</Label>
          <select
            id="wf-objective"
            className="h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm"
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
          >
            {(opts.data?.objectives ?? ['sharpe_ratio']).map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </div>

        <div className="md:col-span-2">
          <Label htmlFor="wf-symbols">Symbols</Label>
          <Input
            id="wf-symbols"
            value={symbolsRaw}
            onChange={(e) => setSymbolsRaw(e.target.value)}
            placeholder="AAPL, MSFT, NVDA"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            {symbols.length} symbol{symbols.length === 1 ? '' : 's'} parsed
          </p>
        </div>

        <div>
          <Label htmlFor="wf-start">Dataset start</Label>
          <Input
            id="wf-start"
            type="date"
            value={datasetStart}
            onChange={(e) => setDatasetStart(e.target.value)}
            required
          />
        </div>

        <div>
          <Label htmlFor="wf-end">Dataset end</Label>
          <Input
            id="wf-end"
            type="date"
            value={datasetEnd}
            onChange={(e) => setDatasetEnd(e.target.value)}
            required
          />
        </div>

        <div>
          <Label htmlFor="wf-train">Train window (days)</Label>
          <Input
            id="wf-train"
            type="number"
            min={30}
            value={trainDays}
            onChange={(e) => setTrainDays(Number(e.target.value))}
            required
          />
        </div>

        <div>
          <Label htmlFor="wf-test">Test window (days)</Label>
          <Input
            id="wf-test"
            type="number"
            min={5}
            value={testDays}
            onChange={(e) => setTestDays(Number(e.target.value))}
            required
          />
        </div>

        <div>
          <Label htmlFor="wf-splits">Splits</Label>
          <Input
            id="wf-splits"
            type="number"
            min={1}
            max={10}
            value={nSplits}
            onChange={(e) => setNSplits(Number(e.target.value))}
            required
          />
        </div>

        <div>
          <Label htmlFor="wf-trials">Trials</Label>
          <Input
            id="wf-trials"
            type="number"
            min={1}
            max={200}
            value={nTrials}
            onChange={(e) => setNTrials(Number(e.target.value))}
            required
          />
        </div>

        <div className="md:col-span-2">
          <Label htmlFor="wf-regime">Regime filter</Label>
          <select
            id="wf-regime"
            className="h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm"
            value={regime ?? ''}
            onChange={(e) =>
              setRegime((e.target.value || null) as RegimeFilter)
            }
          >
            {REGIMES.map((r) => (
              <option key={r ?? 'all'} value={r ?? ''}>
                {r ?? 'All regimes'}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-muted-foreground">
            Restrict scoring to trades whose entry day matches this regime.
          </p>
        </div>

        <div className="md:col-span-2">
          <Label htmlFor="wf-params">Param space (JSON)</Label>
          <textarea
            id="wf-params"
            className="h-44 w-full rounded-md border border-input bg-transparent px-2.5 py-2 font-mono text-xs"
            value={paramSpaceText}
            onChange={(e) => setParamSpaceText(e.target.value)}
            spellCheck={false}
          />
        </div>

        <div className="md:col-span-2 flex items-center justify-end gap-2">
          <Button type="submit" disabled={submitDisabled}>
            {isPending ? 'Enqueuing…' : 'Run study'}
          </Button>
        </div>
      </form>
    </ChartGlassCard>
  );
};

export default StudyForm;
