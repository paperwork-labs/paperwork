const dashboardUrls = (process.env.POSTHOG_DASHBOARD_URL ?? "")
  .split(",")
  .map((url) => url.trim())
  .filter(Boolean);

function configuredItems() {
  return [
    { key: "NEXT_PUBLIC_POSTHOG_HOST", value: process.env.NEXT_PUBLIC_POSTHOG_HOST },
    { key: "NEXT_PUBLIC_POSTHOG_KEY", value: process.env.NEXT_PUBLIC_POSTHOG_KEY },
    { key: "POSTHOG_DASHBOARD_URL", value: process.env.POSTHOG_DASHBOARD_URL },
  ];
}

export default function AnalyticsPage() {
  const config = configuredItems();
  const configuredCount = config.filter((item) => Boolean(item.value)).length;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
      <p className="text-zinc-400">PostHog visibility for growth, activation, and conversion tracking.</p>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Env setup</p>
          <p className="mt-2 text-2xl font-semibold">
            {configuredCount}/{config.length}
          </p>
          <p className="text-sm text-zinc-400">analytics keys configured</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Dashboard embeds</p>
          <p className="mt-2 text-2xl font-semibold">{dashboardUrls.length}</p>
          <p className="text-sm text-zinc-400">shared PostHog links detected</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Data source</p>
          <p className="mt-2 text-2xl font-semibold">PostHog</p>
          <p className="text-sm text-zinc-400">single source of product analytics</p>
        </div>
      </section>

      {dashboardUrls.length > 0 ? (
        <section className="space-y-4">
          {dashboardUrls.map((url) => (
            <div key={url} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
              <p className="mb-2 text-sm text-zinc-300">{url}</p>
              <iframe
                title={`PostHog dashboard ${url}`}
                src={url}
                className="h-96 w-full rounded-lg border border-zinc-800 bg-zinc-950"
                sandbox="allow-scripts allow-same-origin allow-forms"
                referrerPolicy="strict-origin-when-cross-origin"
              />
            </div>
          ))}
        </section>
      ) : (
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-sm text-zinc-300">
            Add a shared dashboard URL in `POSTHOG_DASHBOARD_URL` to embed analytics here. Multiple
            dashboards are supported with comma-separated URLs.
          </p>
          <ul className="mt-3 space-y-2 text-sm text-zinc-400">
            {config.map((item) => (
              <li key={item.key}>
                {item.key}: {item.value ? "configured" : "missing"}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
