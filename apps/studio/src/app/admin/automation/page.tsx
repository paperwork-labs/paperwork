import Link from "next/link";

import {
  defaultDocLinkForName,
  parseAutomationTable,
  readAutomationStateMarkdown,
  type AutomationRow,
} from "@/lib/automation-state";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function colForRow(r: AutomationRow): "live" | "gated" | "shadow" | "broken" {
  if (r.status.includes("🔴")) {
    return "broken";
  }
  if (r.status.includes("🔵")) {
    return "shadow";
  }
  if (r.status.includes("🟡")) {
    return "gated";
  }
  if (r.status.includes("✅")) {
    return "live";
  }
  return "live";
}

function Card({
  r,
  sourceHref,
}: {
  r: AutomationRow;
  sourceHref: string;
}) {
  return (
    <li className="rounded-lg border border-zinc-800/80 bg-zinc-900/40 p-3 text-sm">
      <div className="font-medium text-zinc-200">
        <a
          href={sourceHref}
          target="_blank"
          rel="noreferrer"
          className="text-sky-400 hover:underline"
        >
          {r.name}
        </a>
      </div>
      <p className="mt-1 line-clamp-3 text-xs text-zinc-500">{r.what}</p>
      <p className="mt-1 text-[10px] text-zinc-600">
        {r.schedule} · {r.type}
      </p>
      {r.studio !== "—" && r.studioHref ? (
        <Link
          href={r.studioHref}
          className="mt-2 inline-block text-[10px] text-zinc-500 hover:text-zinc-300"
        >
          {r.studio}
        </Link>
      ) : null}
    </li>
  );
}

export default async function AutomationPage() {
  const md = await readAutomationStateMarkdown();
  if (!md) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold text-zinc-100">Automation</h1>
        <p className="max-w-2xl text-sm text-zinc-400">
          The automation index lives at <code className="text-zinc-300">docs/infra/AUTOMATION_STATE.md</code>{" "}
          in the monorepo. It is not available in this build context yet — open the file on{" "}
          <a
            className="text-sky-400 hover:underline"
            href="https://github.com/paperwork-labs/paperwork/blob/main/docs/infra/AUTOMATION_STATE.md"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>{" "}
          while this PR is in review, or run Studio from the repository root in development.
        </p>
      </div>
    );
  }

  const rows = parseAutomationTable(md);
  const live = rows.filter((r) => colForRow(r) === "live");
  const gated = rows.filter((r) => colForRow(r) === "gated");
  const shadow = rows.filter((r) => colForRow(r) === "shadow");
  const broken = rows.filter((r) => colForRow(r) === "broken");

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-xl font-semibold text-zinc-100">Automation</h1>
        <p className="max-w-3xl text-sm text-zinc-400">
          Parsed from <code className="text-zinc-300">docs/infra/AUTOMATION_STATE.md</code> at runtime.
          Each card links to the listed GitHub source (schedulers, workflows, or this doc).{" "}
          <span className="text-zinc-500">Tally: ✅ {live.length} · 🟡 {gated.length} · 🔵 {shadow.length}</span>
          {broken.length > 0 ? (
            <span className="text-zinc-500"> · 🔴 {broken.length}</span>
          ) : null}
        </p>
      </header>
      {broken.length > 0 ? (
        <section>
          <h2 className="mb-2 text-sm font-medium text-rose-300">Attention (🔴)</h2>
          <ul className="grid gap-2 sm:grid-cols-1 lg:grid-cols-2">
            {broken.map((r) => (
              <Card
                key={r.name + r.type}
                r={r}
                sourceHref={defaultDocLinkForName(r.name, r.nameHref)}
              />
            ))}
          </ul>
        </section>
      ) : null}
      <div className="grid gap-6 lg:grid-cols-3">
        <section>
          <h2 className="mb-2 text-sm font-medium text-emerald-300/90">Live (✅)</h2>
          <ul className="space-y-2">
            {live.map((r) => (
              <Card
                key={r.name + r.type}
                r={r}
                sourceHref={defaultDocLinkForName(r.name, r.nameHref)}
              />
            ))}
          </ul>
        </section>
        <section>
          <h2 className="mb-2 text-sm font-medium text-amber-300/90">Gated (🟡)</h2>
          <ul className="space-y-2">
            {gated.map((r) => (
              <Card
                key={r.name + r.type}
                r={r}
                sourceHref={defaultDocLinkForName(r.name, r.nameHref)}
              />
            ))}
          </ul>
        </section>
        <section>
          <h2 className="mb-2 text-sm font-medium text-sky-300/90">Shadow (🔵)</h2>
          <ul className="space-y-2">
            {shadow.map((r) => (
              <Card
                key={r.name + r.type}
                r={r}
                sourceHref={defaultDocLinkForName(r.name, r.nameHref)}
              />
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
