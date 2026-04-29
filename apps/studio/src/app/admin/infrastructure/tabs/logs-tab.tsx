import { ScrollText } from "lucide-react";

// PR M wires live log streaming into this tab.
export default function LogsTab() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-700 bg-zinc-900/40 py-16 text-center">
        <ScrollText className="mb-4 h-10 w-10 text-zinc-600" />
        <h2 className="text-base font-semibold text-zinc-300">Logs — coming soon</h2>
        <p className="mt-2 max-w-sm text-sm text-zinc-500">
          Aggregated log streaming across Render, Vercel, and Brain. PR M wires
          live log ingestion into this tab.
        </p>
        <span className="mt-4 rounded-full border border-zinc-700 bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-400">
          PR M populates
        </span>
      </div>
    </div>
  );
}
