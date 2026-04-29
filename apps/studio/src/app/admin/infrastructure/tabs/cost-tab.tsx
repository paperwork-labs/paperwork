import { DollarSign } from "lucide-react";

export default function CostTab() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-700 bg-zinc-900/40 py-16 text-center">
        <DollarSign className="mb-4 h-10 w-10 text-zinc-600" />
        <h2 className="text-base font-semibold text-zinc-300">Cost dashboard</h2>
        <p className="mt-2 max-w-sm text-sm text-zinc-500">
          Cost dashboard ships in WS-74 phase 2.
        </p>
        <span className="mt-4 rounded-full border border-zinc-700 bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-400">
          WS-74 phase 2
        </span>
      </div>
    </div>
  );
}
