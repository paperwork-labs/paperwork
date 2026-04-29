import type { ExpenseRoutingRules } from "@/lib/expenses";
import { formatCents, CATEGORY_LABELS } from "@/lib/expenses";

type Props = {
  rules: ExpenseRoutingRules | null;
};

export function SettingsTab({ rules }: Props) {
  if (!rules) {
    return (
      <p className="py-8 text-center text-sm text-zinc-500">
        Brain unavailable — routing rules not loaded.
      </p>
    );
  }

  const thresholdLabel =
    rules.auto_approve_threshold_cents === 0
      ? "None (every expense requires approval)"
      : formatCents(rules.auto_approve_threshold_cents);

  return (
    <div className="space-y-6 max-w-lg">
      <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-5 space-y-4">
        <h2 className="text-sm font-semibold text-zinc-200">Auto-approve threshold</h2>
        <div className="space-y-1">
          <p className="text-xs text-zinc-500 uppercase tracking-wide font-semibold">Threshold</p>
          <p className="text-sm text-zinc-200">{thresholdLabel}</p>
          {rules.auto_approve_threshold_cents === 0 && (
            <p className="text-xs text-amber-400/80">
              ⚠ Defaulting to $0 — every expense is initially pending.
            </p>
          )}
        </div>
        {rules.auto_approve_categories.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs text-zinc-500 uppercase tracking-wide font-semibold">
              Auto-approved categories
            </p>
            <p className="text-sm text-zinc-200">
              {rules.auto_approve_categories
                .map((c) => CATEGORY_LABELS[c] ?? c)
                .join(", ")}
            </p>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-5 space-y-4">
        <h2 className="text-sm font-semibold text-zinc-200">Auto-flag rules</h2>
        <div className="space-y-1">
          <p className="text-xs text-zinc-500 uppercase tracking-wide font-semibold">
            Flag threshold
          </p>
          <p className="text-sm text-zinc-200">
            {formatCents(rules.flagged_threshold_cents)} and above
          </p>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-zinc-500 uppercase tracking-wide font-semibold">
            Always-flag categories
          </p>
          <p className="text-sm text-zinc-200">
            {rules.flagged_categories.length > 0
              ? rules.flagged_categories.map((c) => CATEGORY_LABELS[c] ?? c).join(", ")
              : "None"}
          </p>
        </div>
      </div>

      <p className="text-xs text-zinc-600">
        Routing rules are editable in PR O (WS-69). For now these settings are read-only.
      </p>
    </div>
  );
}
