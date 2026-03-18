import { getInfrastructureStatus } from "@/lib/command-center";

function statusColor(ok: boolean) {
  return ok ? "text-emerald-300" : "text-rose-300";
}

export default async function InfrastructurePage() {
  const services = await getInfrastructureStatus();
  const healthyCount = services.filter((s) => s.healthy).length;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Infrastructure Health</h1>
      <p className="text-zinc-400">
        Live checks across command-center dependencies and external provider APIs.
      </p>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Healthy services</p>
          <p className="mt-2 text-2xl font-semibold">
            {healthyCount}/{services.length}
          </p>
        </div>
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <div className="space-y-3">
          {services.map((service) => (
            <div
              key={service.service}
              className="flex items-center justify-between rounded-md bg-zinc-800/60 px-3 py-3 text-sm"
            >
              <div>
                <p className="font-medium text-zinc-100">{service.service}</p>
                <p className="text-zinc-400">{service.detail}</p>
              </div>
              <div className="text-right">
                <p className={statusColor(service.healthy)}>
                  {service.healthy ? "healthy" : "degraded"}
                </p>
                <p className="text-xs text-zinc-500">
                  {service.configured ? "configured" : "not configured"}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
