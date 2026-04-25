import Link from "next/link";
import { ArrowRight, Radar, Sparkles, Wallet } from "lucide-react";

export default function HomePage() {
  const cards = [
    {
      href: "/system-status",
      label: "System Status",
      description:
        "Medallion layers, broker sync health, data-quality checks. The canonical health dashboard.",
      Icon: Sparkles,
    },
    {
      href: "/portfolio",
      label: "Portfolio",
      description:
        "Positions, income, holdings, and workspace editors. Reads gold-layer views over the API.",
      Icon: Wallet,
    },
    {
      href: "/scanner",
      label: "Scanner",
      description:
        "Strategy-native scanner with stage analysis + IV rank. Pulls signals from the gold layer.",
      Icon: Radar,
    },
  ];
  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <p className="text-xs uppercase tracking-[0.2em] text-sky-400">Track E preview</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          AxiomFolio, on Next.js
        </h1>
        <p className="max-w-3xl text-base text-zinc-400">
          This is the scaffolded Next.js 16 shell running alongside the existing
          Vite app. Three core routes ship first — <strong>System Status</strong>,{" "}
          <strong>Portfolio</strong>, and <strong>Scanner</strong> — behind the{" "}
          <code className="rounded bg-zinc-900 px-1 py-0.5 text-xs text-amber-300">
            NEXT_PUBLIC_AXIOMFOLIO_NEXT_ENABLED
          </code>{" "}
          feature flag. Middleware redirects back to the Vite app until a route
          opts in.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {cards.map((card) => {
          const { Icon } = card;
          return (
            <Link
              key={card.href}
              href={card.href}
              className="group rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 transition hover:border-zinc-700 hover:bg-zinc-900"
            >
              <Icon className="h-5 w-5 text-sky-300" />
              <h2 className="mt-3 text-sm font-semibold text-zinc-100 group-hover:text-white">
                {card.label}
              </h2>
              <p className="mt-2 text-xs text-zinc-400">{card.description}</p>
              <span className="mt-4 inline-flex items-center gap-1 text-[11px] uppercase tracking-wide text-zinc-500 group-hover:text-sky-300">
                open <ArrowRight className="h-3 w-3" />
              </span>
            </Link>
          );
        })}
      </section>
    </div>
  );
}
