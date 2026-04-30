"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { FilterChipRow } from "@paperwork-labs/ui";
import { History, Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import type { Expense, ExpenseCategory, ExpenseRoutingRules } from "@/types/expenses";
import { CATEGORY_LABELS, formatCents } from "@/types/expenses";

const ALL_CATEGORIES = Object.keys(CATEGORY_LABELS) as ExpenseCategory[];

type Props = {
  rules: ExpenseRoutingRules | null;
  onRulesSaved?: (next: ExpenseRoutingRules) => void;
};

type HistoryEntry = {
  at?: string;
  updated_by?: string;
  diff?: Record<string, { from?: unknown; to?: unknown }>;
};

function dollarsWholeToCents(d: number): number {
  if (!Number.isFinite(d) || d < 0) return 0;
  return Math.round(d * 100);
}

function centsToWholeDollars(cents: number): number {
  return Math.floor(cents / 100);
}

/** Mirror Brain ``_routing_decision`` for client-side preview. */
function previewOutcome(
  amount_cents: number,
  category: ExpenseCategory,
  r: Pick<
    ExpenseRoutingRules,
    | "auto_approve_threshold_cents"
    | "auto_approve_categories"
    | "always_review_categories"
    | "flag_amount_cents_above"
  >,
): "auto" | "approval" {
  if (amount_cents > r.flag_amount_cents_above) return "approval";
  if (r.always_review_categories.includes(category)) return "approval";
  if (
    r.auto_approve_threshold_cents > 0 &&
    amount_cents < r.auto_approve_threshold_cents &&
    r.auto_approve_categories.includes(category)
  ) {
    return "auto";
  }
  return "approval";
}

export function SettingsTab({ rules, onRulesSaved }: Props) {
  const [previewExpenses, setPreviewExpenses] = useState<Expense[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(true);

  const [thresholdDollars, setThresholdDollars] = useState(0);
  const [flagDollars, setFlagDollars] = useState(1000);
  const [autoCats, setAutoCats] = useState<Set<ExpenseCategory>>(
    () => new Set(rules?.auto_approve_categories ?? []),
  );
  const [alwaysCats, setAlwaysCats] = useState<Set<ExpenseCategory>>(
    () => new Set(rules?.always_review_categories ?? []),
  );
  const [initialKey, setInitialKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const baselineThresholdCents = rules?.auto_approve_threshold_cents ?? 0;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingPreview(true);
      try {
        const res = await fetch("/api/admin/expenses?limit=500");
        const json = await res.json();
        if (!cancelled && json.success && json.data?.items) {
          setPreviewExpenses(json.data.items as Expense[]);
        }
      } finally {
        if (!cancelled) setLoadingPreview(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!rules) return;
    setThresholdDollars(centsToWholeDollars(rules.auto_approve_threshold_cents));
    setFlagDollars(centsToWholeDollars(rules.flag_amount_cents_above));
    setAutoCats(new Set(rules.auto_approve_categories));
    setAlwaysCats(new Set(rules.always_review_categories));
    setInitialKey(
      JSON.stringify({
        t: rules.auto_approve_threshold_cents,
        f: rules.flag_amount_cents_above,
        a: [...rules.auto_approve_categories].sort(),
        w: [...rules.always_review_categories].sort(),
      }),
    );
  }, [rules]);

  const draftRules = useMemo(
    (): Pick<
      ExpenseRoutingRules,
      | "auto_approve_threshold_cents"
      | "auto_approve_categories"
      | "always_review_categories"
      | "flag_amount_cents_above"
    > => ({
      auto_approve_threshold_cents: dollarsWholeToCents(thresholdDollars),
      auto_approve_categories: [...autoCats],
      always_review_categories: [...alwaysCats],
      flag_amount_cents_above: dollarsWholeToCents(flagDollars),
    }),
    [thresholdDollars, flagDollars, autoCats, alwaysCats],
  );

  const currentKey = JSON.stringify({
    t: draftRules.auto_approve_threshold_cents,
    f: draftRules.flag_amount_cents_above,
    a: [...draftRules.auto_approve_categories].sort(),
    w: [...draftRules.always_review_categories].sort(),
  });

  const dirty = Boolean(rules) && currentKey !== initialKey;

  const previewStats = useMemo(() => {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 30);
    const ymd = cutoff.toISOString().slice(0, 10);
    const recent = previewExpenses.filter((e) => e.occurred_at >= ymd);
    let wouldAuto = 0;
    let wasApproval = 0;
    let wouldRoute = 0;
    for (const e of recent) {
      const nowOutcome = previewOutcome(e.amount_cents, e.category, {
        auto_approve_threshold_cents: baselineThresholdCents,
        auto_approve_categories: rules?.auto_approve_categories ?? [],
        always_review_categories: rules?.always_review_categories ?? [],
        flag_amount_cents_above: rules?.flag_amount_cents_above ?? 100000,
      });
      const nextOutcome = previewOutcome(e.amount_cents, e.category, draftRules);
      if (nextOutcome === "auto") {
        wouldAuto += 1;
        if (nowOutcome === "approval") wasApproval += 1;
      } else {
        wouldRoute += 1;
      }
    }
    return { wouldAuto, wasApproval, wouldRoute, sampleSize: recent.length };
  }, [previewExpenses, draftRules, rules, baselineThresholdCents]);

  const toggleAuto = useCallback(
    (cat: ExpenseCategory) => {
      setAutoCats((prev) => {
        const next = new Set(prev);
        if (next.has(cat)) next.delete(cat);
        else {
          next.add(cat);
          setAlwaysCats((a) => {
            const na = new Set(a);
            na.delete(cat);
            return na;
          });
        }
        return next;
      });
    },
    [],
  );

  const toggleAlways = useCallback(
    (cat: ExpenseCategory) => {
      setAlwaysCats((prev) => {
        const next = new Set(prev);
        if (next.has(cat)) next.delete(cat);
        else {
          next.add(cat);
          setAutoCats((a) => {
            const na = new Set(a);
            na.delete(cat);
            return na;
          });
        }
        return next;
      });
    },
    [],
  );

  async function handleSave() {
    if (!rules) return;
    setError(null);
    const tCents = dollarsWholeToCents(thresholdDollars);
    const fCents = dollarsWholeToCents(flagDollars);
    if (fCents < tCents) {
      setError("Flag-above amount must be greater than or equal to the auto-approve threshold.");
      return;
    }
    setSaving(true);
    try {
      const body = {
        auto_approve_threshold_cents: tCents,
        auto_approve_categories: [...autoCats],
        always_review_categories: [...alwaysCats],
        flag_amount_cents_above: fCents,
        founder_card_default_source: rules.founder_card_default_source,
        subscription_skip_approval: rules.subscription_skip_approval,
        updated_by: "founder",
      };
      const res = await fetch("/api/admin/expenses/rules", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const json = await res.json();
      if (!res.ok || !json.success) {
        throw new Error(json.error ?? "Save failed");
      }
      const next = json.data as ExpenseRoutingRules;
      const raised = tCents > baselineThresholdCents;
      if (raised) {
        toast.success("Rules updated · audit Conversation created", {
          description: "Open Conversations and filter by tag expense-rule-change.",
        });
      } else {
        toast.success("Rules updated");
      }
      onRulesSaved?.(next);
      setInitialKey(
        JSON.stringify({
          t: next.auto_approve_threshold_cents,
          f: next.flag_amount_cents_above,
          a: [...next.auto_approve_categories].sort(),
          w: [...next.always_review_categories].sort(),
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!rules) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 text-center">
        <p className="text-sm text-zinc-500">
          Could not load routing rules. Check Brain API connectivity.
        </p>
      </div>
    );
  }

  const history = (rules.history ?? []).slice(-10).reverse() as HistoryEntry[];

  return (
    <section className="space-y-8">
      {error ? (
        <div className="rounded-lg border border-red-800/50 bg-red-900/20 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
        <h2 className="text-sm font-semibold text-zinc-100">Auto-approve threshold</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Expenses below this amount in the categories below will auto-approve. Set to $0 to require
          approval on everything (recommended for first 30 days).
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <label className="text-xs text-zinc-500" htmlFor="threshold-input">
            Threshold ($)
          </label>
          <input
            id="threshold-input"
            type="number"
            min={0}
            step={50}
            value={thresholdDollars}
            onChange={(e) => setThresholdDollars(Number(e.target.value) || 0)}
            className="w-40 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
          />
          <span className="text-xs text-zinc-500">({formatCents(draftRules.auto_approve_threshold_cents)})</span>
        </div>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6" data-testid="settings-auto-categories">
        <h3 className="text-sm font-semibold text-zinc-100">Auto-approve categories</h3>
        <p className="mt-1 text-xs text-zinc-500">Toggle categories; a category cannot be in both lists.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {ALL_CATEGORIES.map((cat) => (
            <FilterChipRow
              key={`auto-${cat}`}
              chips={[{ id: cat, label: CATEGORY_LABELS[cat] }]}
              value={autoCats.has(cat) ? cat : "_off_"}
              onChange={() => toggleAuto(cat)}
            />
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6" data-testid="settings-always-categories">
        <h3 className="text-sm font-semibold text-zinc-100">Always-review categories</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {ALL_CATEGORIES.map((cat) => (
            <FilterChipRow
              key={`always-${cat}`}
              chips={[{ id: cat, label: CATEGORY_LABELS[cat] }]}
              value={alwaysCats.has(cat) ? cat : "_off_"}
              onChange={() => toggleAlways(cat)}
            />
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
        <h3 className="text-sm font-semibold text-zinc-100">Flag above</h3>
        <p className="mt-1 text-xs text-zinc-500">
          Amounts above this (in addition to routing) set status to flagged and always open an
          approval thread.
        </p>
        <input
          type="number"
          min={0}
          step={50}
          value={flagDollars}
          onChange={(e) => setFlagDollars(Number(e.target.value) || 0)}
          className="mt-3 w-40 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
        />
        <span className="mt-3 ml-2 text-xs text-zinc-500">
          ({formatCents(draftRules.flag_amount_cents_above)} — default $1,000)
        </span>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-6">
        <h3 className="text-sm font-semibold text-zinc-100">Live preview (last 30 days)</h3>
        {loadingPreview ? (
          <p className="mt-2 text-xs text-zinc-500">Loading expenses…</p>
        ) : (
          <p className="mt-2 text-sm text-zinc-300">
            Under new rules:{" "}
            <span className="font-medium text-zinc-100">{previewStats.wouldAuto}</span> would have
            auto-approved
            {previewStats.wasApproval > 0 ? (
              <>
                {" "}
                (<span className="text-zinc-400">{previewStats.wasApproval}</span> were approval
                routed before)
              </>
            ) : null}
            ;{" "}
            <span className="font-medium text-zinc-100">{previewStats.wouldRoute}</span> would have
            routed for approval — sample of <span className="text-zinc-400">{previewStats.sampleSize}</span>{" "}
            expenses with occurred_at in range.
          </p>
        )}
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/20 p-6">
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4 text-zinc-500" />
          <h3 className="text-sm font-semibold text-zinc-100">Recent changes</h3>
        </div>
        {history.length === 0 ? (
          <p className="text-xs text-zinc-600">No history yet.</p>
        ) : (
          <ul className="space-y-3 text-xs text-zinc-400">
            {history.map((h, i) => (
              <li key={`${h.at ?? i}-${i}`} className="rounded-lg border border-zinc-800/80 bg-zinc-950/40 p-3">
                <div className="font-medium text-zinc-300">
                  {h.updated_by ?? "unknown"} · {h.at ? new Date(h.at).toLocaleString() : "—"}
                </div>
                {h.diff && Object.keys(h.diff).length > 0 ? (
                  <ul className="mt-2 space-y-1 font-mono text-[11px] text-zinc-500">
                    {Object.entries(h.diff).map(([k, v]) => (
                      <li key={k}>
                        <span className="text-zinc-400">{k}</span>:{" "}
                        {JSON.stringify(v?.from)} → {JSON.stringify(v?.to)}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-zinc-600">(no field diff recorded)</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          data-testid="settings-save-rules"
          disabled={!dirty || saving}
          onClick={() => void handleSave()}
          className="inline-flex items-center gap-2 rounded-lg bg-sky-500/20 px-4 py-2 text-sm font-medium text-sky-200 ring-1 ring-sky-500/40 transition hover:bg-sky-500/30 disabled:opacity-40"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save changes
        </button>
      </div>
    </section>
  );
}
