import { Info } from "lucide-react";

// PR J will populate this with real integration management UI.
// For now: decommissioned-status notice + forward pointer.

const DECOMMISSIONED = [
  {
    name: "n8n",
    status: "decommissioned",
    note: "Decommissioned in PR J. All workflows migrated to Brain-native triggers or archived.",
  },
  {
    name: "Slack (n8n bot)",
    status: "decommissioned",
    note: "Slack notifications now route through Brain persona webhooks (see Brain → Conversations).",
  },
];

const ACTIVE = [
  {
    name: "Slack (Brain)",
    status: "active",
    note: "Brain sends structured alerts via the #ops channel. Config lives in BRAIN_SLACK_WEBHOOK env var.",
  },
  {
    name: "GitHub",
    status: "active",
    note: "PR pipeline events feed the Studio PR Pipeline page. Token: GITHUB_TOKEN.",
  },
  {
    name: "Vercel",
    status: "active",
    note: "Deployment health probed via Vercel API. Token: VERCEL_TOKEN.",
  },
];

function statusDot(status: "active" | "decommissioned") {
  return (
    <span
      className={[
        "inline-block h-2 w-2 rounded-full",
        status === "active"
          ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.7)]"
          : "bg-zinc-600",
      ].join(" ")}
    />
  );
}

export default function IntegrationsTab() {
  return (
    <div className="space-y-8">
      <div className="flex items-start gap-3 rounded-xl border border-amber-900/50 bg-amber-950/20 p-4 text-sm text-amber-200">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
        <p>
          Full integration management UI ships in{" "}
          <strong className="font-semibold">PR J</strong>. n8n is decommissioned;
          Brain-native webhooks are the new integration layer.
        </p>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
          Active integrations
        </h2>
        <div className="space-y-2">
          {ACTIVE.map((item) => (
            <div
              key={item.name}
              className="flex items-start gap-3 rounded-lg border border-zinc-800 bg-zinc-900/60 p-4"
            >
              <div className="mt-1">{statusDot("active")}</div>
              <div>
                <p className="font-medium text-zinc-100">{item.name}</p>
                <p className="mt-0.5 text-sm text-zinc-400">{item.note}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
          Decommissioned
        </h2>
        <div className="space-y-2">
          {DECOMMISSIONED.map((item) => (
            <div
              key={item.name}
              className="flex items-start gap-3 rounded-lg border border-zinc-800/50 bg-zinc-900/30 p-4 opacity-60"
            >
              <div className="mt-1">{statusDot("decommissioned")}</div>
              <div>
                <p className="font-medium text-zinc-300">{item.name}</p>
                <p className="mt-0.5 text-sm text-zinc-500">{item.note}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
