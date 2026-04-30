import { Construction, ExternalLink } from "lucide-react";

// No /admin/cron or /admin/scheduled-jobs route exists yet (WS-69 PR C
// audit). This tab is reserved for scheduled job management. PR M will fill
// it with real content once Vercel Cron + Render Cron visibility is built.

const KNOWN_CRONS = [
  {
    name: "Brain self-improvement loop",
    schedule: "Every 24 h",
    service: "Brain API (Render)",
    status: "active",
    docs: "https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/README.md",
  },
  {
    name: "Portfolio position refresh",
    schedule: "Every 15 min (market hours)",
    service: "AxiomFolio API (Render)",
    status: "active",
    docs: "https://github.com/paperwork-labs/paperwork/blob/main/apis/axiomfolio",
  },
  {
    name: "Secrets rotation reminder",
    schedule: "Weekly Monday 09:00 PT",
    service: "Brain API",
    status: "active",
    docs: "https://github.com/paperwork-labs/paperwork/blob/main/docs/infra/SECRETS_ROTATION.md",
  },
];

function statusDot(status: string) {
  return (
    <span
      className={[
        "mt-1 inline-block h-2 w-2 shrink-0 rounded-full",
        status === "active"
          ? "bg-[var(--status-success)] shadow-[0_0_6px_rgba(16,185,129,0.7)]"
          : "bg-zinc-600",
      ].join(" ")}
    />
  );
}

export default function CronTab() {
  return (
    <div className="space-y-6">
      <div className="flex items-start gap-3 rounded-xl border border-zinc-800 bg-zinc-900/30 p-4 text-sm text-zinc-400">
        <Construction className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500" />
        <p>
          Full cron management UI (add / disable / inspect runs) ships in{" "}
          <strong className="font-semibold text-zinc-200">PR M</strong>. The
          list below is a static catalogue derived from code — not live
          execution state.
        </p>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
          Known scheduled jobs
        </h2>
        <div className="space-y-2">
          {KNOWN_CRONS.map((cron) => (
            <div
              key={cron.name}
              className="flex items-start gap-3 rounded-lg border border-zinc-800 bg-zinc-900/60 p-4"
            >
              {statusDot(cron.status)}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-medium text-zinc-100">{cron.name}</p>
                  <span className="font-mono text-xs text-zinc-500">{cron.schedule}</span>
                </div>
                <p className="mt-0.5 text-sm text-zinc-500">{cron.service}</p>
              </div>
              <a
                href={cron.docs}
                target="_blank"
                rel="noreferrer"
                className="shrink-0 text-zinc-600 transition hover:text-zinc-300"
                aria-label={`Docs for ${cron.name}`}
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
