import { getProviderCosts, ProviderCost } from "@/lib/provider-costs";

function StatusBadge({ status }: { status: ProviderCost["status"] }) {
  const colors = {
    active: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    inactive: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
    degraded: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${colors[status]}`}
    >
      {status}
    </span>
  );
}

function ProviderCard({ provider }: { provider: ProviderCost }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-100">
          {provider.name}
        </h3>
        <StatusBadge status={provider.status} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-zinc-500 uppercase tracking-wide">
            Monthly Cost
          </p>
          <p className="text-lg font-mono text-zinc-100">
            ${provider.monthlyCost.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500 uppercase tracking-wide">
            API Calls (month)
          </p>
          <p className="text-lg font-mono text-zinc-100">
            {provider.apiCalls.toLocaleString()}
          </p>
        </div>
      </div>

      <p className="text-xs text-zinc-600">
        Last checked: {new Date(provider.lastChecked).toLocaleString()}
      </p>
    </div>
  );
}

export default function ProvidersPage() {
  const providers = getProviderCosts();
  const totalMonthlyCost = providers.reduce(
    (sum, p) => sum + p.monthlyCost,
    0
  );
  const totalApiCalls = providers.reduce((sum, p) => sum + p.apiCalls, 0);

  return (
    <div className="min-h-screen bg-zinc-950 p-8">
      <div className="max-w-5xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">
            Market Data Providers
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Cost tracking and usage for all market data API providers.
          </p>
        </div>

        {/* Summary */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
            <p className="text-xs text-zinc-500 uppercase tracking-wide">
              Total Monthly Cost
            </p>
            <p className="text-2xl font-mono text-zinc-100 mt-1">
              ${totalMonthlyCost.toFixed(2)}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
            <p className="text-xs text-zinc-500 uppercase tracking-wide">
              Total API Calls
            </p>
            <p className="text-2xl font-mono text-zinc-100 mt-1">
              {totalApiCalls.toLocaleString()}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
            <p className="text-xs text-zinc-500 uppercase tracking-wide">
              Active Providers
            </p>
            <p className="text-2xl font-mono text-zinc-100 mt-1">
              {providers.filter((p) => p.status === "active").length} /{" "}
              {providers.length}
            </p>
          </div>
        </div>

        {/* Provider Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {providers.map((provider) => (
            <ProviderCard key={provider.name} provider={provider} />
          ))}
        </div>
      </div>
    </div>
  );
}
