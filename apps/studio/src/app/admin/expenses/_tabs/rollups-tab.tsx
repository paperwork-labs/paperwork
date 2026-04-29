import { fetchRollup } from "@/lib/expenses";
import { RollupCard } from "../_components/rollup-card";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

function exportUrl(brainRoot: string | null, period: string, year: number, month: number) {
  if (!brainRoot) return "#";
  const params = new URLSearchParams({
    format: "csv",
    period,
    year: String(year),
    month: String(month),
  });
  return `${brainRoot}/admin/expenses/export?${params}`;
}

export async function RollupsTab() {
  const now = new Date();
  const thisYear = now.getFullYear();
  const thisMonth = now.getMonth() + 1;

  const prevMonth = thisMonth === 1 ? 12 : thisMonth - 1;
  const prevMonthYear = thisMonth === 1 ? thisYear - 1 : thisYear;

  const [thisMonthRollup, prevMonthRollup, thisQtrRollup] = await Promise.all([
    fetchRollup("month", thisYear, thisMonth),
    fetchRollup("month", prevMonthYear, prevMonth),
    fetchRollup("quarter", thisYear, thisMonth),
  ]);

  const auth = getBrainAdminFetchOptions();
  const brainRoot = auth.ok ? auth.root : null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-sm font-semibold text-zinc-200">Expense Rollups</h2>
        <p className="text-xs text-zinc-500">
          Monthly and quarterly breakdowns. Download CSV for accounting.
        </p>
      </div>

      {!thisMonthRollup && !prevMonthRollup && !thisQtrRollup ? (
        <p className="py-8 text-center text-sm text-zinc-500">
          Brain unavailable — rollup data not loaded.
        </p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {thisMonthRollup && (
            <RollupCard
              rollup={thisMonthRollup}
              exportUrl={exportUrl(brainRoot, "month", thisYear, thisMonth)}
            />
          )}
          {prevMonthRollup && (
            <RollupCard
              rollup={prevMonthRollup}
              exportUrl={exportUrl(brainRoot, "month", prevMonthYear, prevMonth)}
            />
          )}
          {thisQtrRollup && (
            <RollupCard
              rollup={thisQtrRollup}
              exportUrl={exportUrl(brainRoot, "quarter", thisYear, thisMonth)}
            />
          )}
        </div>
      )}
    </div>
  );
}
