import { getInfrastructureStatus } from "@/lib/command-center";
import Link from "next/link";

function statusTone(healthy: boolean, configured: boolean) {
  if (!configured) return "text-amber-300";
  return healthy ? "text-emerald-300" : "text-rose-300";
}

function statusLabel(healthy: boolean, configured: boolean) {
  if (!configured) return "not configured";
  return healthy ? "healthy" : "down";
}

function serviceIcon(service: string) {
  switch (service.toLowerCase()) {
    case "n8n":
      return "workflow";
    case "postiz":
      return "social";
    case "render":
      return "compute";
    case "vercel":
      return "web";
    case "neon":
      return "database";
    case "upstash redis":
      return "cache";
    default:
      return "service";
  }
}

export default async function InfrastructurePage() {
  const services = await getInfrastructureStatus();
  const healthyCount = services.filter((s) => s.healthy).length;
  const configuredCount = services.filter((s) => s.configured).length;
  const degradedCount = services.filter((s) => s.configured && !s.healthy).length;
  const checkedAt = new Date().toISOString();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Infrastructure Health</h1>
      <p className="text-zinc-400">
        Live checks across command-center dependencies and external provider APIs.
      </p>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Overall score</p>
          <p className="mt-2 text-2xl font-semibold">
            {healthyCount}/{services.length}
          </p>
          <p className="text-sm text-zinc-400">services healthy</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Configured</p>
          <p className="mt-2 text-2xl font-semibold">
            {configuredCount}/{services.length}
          </p>
          <p className="text-sm text-zinc-400">provider keys or URLs present</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Degraded</p>
          <p className="mt-2 text-2xl font-semibold">{degradedCount}</p>
          <p className="text-sm text-zinc-400">configured services with failures</p>
        </div>
      </section>

      <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
        <p className="text-sm text-zinc-300">
          Last checked: <span className="text-zinc-100">{checkedAt}</span>
        </p>
        <Link
          href={`/admin/infrastructure?refresh=${Date.now()}`}
          className="rounded-md border border-zinc-700 px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-800 hover:text-zinc-100"
        >
          Refresh checks
        </Link>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {services.map((service) => (
          <div key={service.service} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-zinc-500">{serviceIcon(service.service)}</p>
                <p className="mt-1 text-lg font-medium text-zinc-100">{service.service}</p>
              </div>
              <p className={`text-sm font-medium ${statusTone(service.healthy, service.configured)}`}>
                {statusLabel(service.healthy, service.configured)}
              </p>
            </div>
            <p className="mt-3 text-sm text-zinc-400">{service.detail}</p>
          </div>
        ))}
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="mb-3 text-sm font-medium text-zinc-200">Raw status view</p>
        <div className="space-y-3">
          {services.map((service) => (
            <div
              key={`${service.service}-raw`}
              className="flex items-center justify-between rounded-md bg-zinc-800/60 px-3 py-3 text-sm"
            >
              <div>
                <p className="font-medium text-zinc-100">{service.service}</p>
                <p className="text-zinc-400">{service.detail}</p>
              </div>
              <div className="text-right">
                <p className={statusTone(service.healthy, service.configured)}>
                  {statusLabel(service.healthy, service.configured)}
                </p>
                <p className="text-xs text-zinc-500">
                  {service.configured ? "configured" : "missing config"}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
