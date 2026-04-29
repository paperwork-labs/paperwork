import { Shield, Server, Database, Globe, HardDrive, Activity } from "lucide-react";

const OVERVIEW_SECTIONS = [
  {
    icon: Shield,
    title: "Services",
    description:
      "Live probe of all deployed services — Render APIs, Vercel frontends, Redis, Neon Postgres, and external integrations. Use the Services tab for health details.",
    tab: "services",
  },
  {
    icon: Database,
    title: "Secrets Vault",
    description:
      "Inventory of all service credentials, API keys, and token rotation status tracked in the database. Use the Secrets tab to manage.",
    tab: "secrets",
  },
  {
    icon: Activity,
    title: "Logs",
    description:
      "Aggregated log viewer across Render, Vercel, and Brain. PR M wires live log streaming into the Logs tab.",
    tab: "logs",
    comingSoon: true,
    owner: "PR M",
  },
  {
    icon: HardDrive,
    title: "Cost",
    description: "Cost dashboard ships in WS-74 phase 2.",
    tab: "cost",
    comingSoon: true,
    owner: "WS-74",
  },
];

export default function InfraOverviewTab() {
  return (
    <div className="space-y-6">
      <p className="text-sm text-zinc-400">
        Infrastructure overview — click any section to navigate to the detail tab.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {OVERVIEW_SECTIONS.map((section) => {
          const Icon = section.icon;
          return (
            <div
              key={section.title}
              className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
            >
              <div className="mb-2 flex items-center gap-2">
                <Icon className="h-4 w-4 text-zinc-400" />
                <h2 className="font-semibold text-zinc-100">{section.title}</h2>
                {section.comingSoon ? (
                  <span className="ml-auto rounded-full border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-[10px] font-medium text-zinc-400">
                    {section.owner}
                  </span>
                ) : null}
              </div>
              <p className="text-sm leading-relaxed text-zinc-400">{section.description}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
