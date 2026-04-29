import { Settings, Lock } from "lucide-react";
import type { ExpenseRoutingRules } from "@/types/expenses";
import { CATEGORY_LABELS, formatCents } from "@/types/expenses";

type Props = {
  rules: ExpenseRoutingRules | null;
};

export function SettingsTab({ rules }: Props) {
  if (!rules) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 text-center">
        <p className="text-sm text-zinc-500">
          Could not load routing rules. Check Brain API connectivity.
        </p>
      </div>
    );
  }

  return (
    <section className="space-y-6">
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
        <div className="mb-5 flex items-center gap-2">
          <Settings className="h-4 w-4 text-zinc-500" />
          <h2 className="text-sm font-semibold text-zinc-100">Expense routing rules</h2>
          <span className="ml-auto rounded bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300 ring-1 ring-amber-500/20">
            Read-only in PR N
          </span>
        </div>

        <div className="space-y-4 text-sm">
          <Row
            label="Auto-approve threshold"
            value={
              rules.auto_approve_threshold_cents === 0
                ? "$0 — all expenses route for approval"
                : formatCents(rules.auto_approve_threshold_cents)
            }
          />
          <Row
            label="Auto-approve categories"
            value={
              rules.auto_approve_categories.length === 0
                ? "None"
                : rules.auto_approve_categories
                    .map((c) => CATEGORY_LABELS[c] ?? c)
                    .join(", ")
            }
          />
          <Row
            label="Always-review categories"
            value={
              rules.always_review_categories.length === 0
                ? "None"
                : rules.always_review_categories
                    .map((c) => CATEGORY_LABELS[c] ?? c)
                    .join(", ")
            }
          />
          <Row
            label="Flag threshold"
            value={`>${formatCents(rules.flag_amount_cents_above)}`}
          />
          <Row label="Last updated by" value={rules.updated_by} />
          <Row
            label="Last updated at"
            value={new Date(rules.updated_at).toLocaleString("en-US", {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          />
        </div>
      </div>

      <div className="flex items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/20 px-5 py-4">
        <Lock className="h-4 w-4 shrink-0 text-zinc-600" />
        <div>
          <p className="text-sm font-medium text-zinc-300">Rules editor</p>
          <p className="text-xs text-zinc-500">
            The live rules editor (threshold slider, category toggles, flag keywords) ships in{" "}
            <span className="font-medium text-zinc-400">PR O</span> — Expenses ↔ Conversations
            wiring.
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/20 px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Audit log
        </p>
        <p className="mt-1 text-xs text-zinc-600">
          Rule-change audit log ships in PR O. Each threshold change will create an info-level
          Conversation recording who changed what and when.
        </p>
      </div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-6">
      <span className="text-zinc-500">{label}</span>
      <span className="text-right font-medium text-zinc-200">{value}</span>
    </div>
  );
}
