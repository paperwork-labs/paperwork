import { ArrowUpRight } from "lucide-react";

const products = [
  {
    name: "FileFree",
    domain: "filefree.ai",
    description: "Free tax filing. Snap a W2, get your return in minutes.",
    gradient: "from-violet-500 to-purple-600",
    status: "January 2027",
  },
  {
    name: "LaunchFree",
    domain: "launchfree.ai",
    description:
      "Free LLC formation. AI picks your best state, we file the paperwork.",
    gradient: "from-teal-400 to-cyan-500",
    status: "Summer 2026",
  },
  {
    name: "Distill",
    domain: "distill.tax",
    description:
      "Compliance automation for modern platforms. Tax API, Formation API, CPA SaaS.",
    gradient: "from-blue-500 to-blue-800",
    status: "Summer 2026",
  },
  {
    name: "Trinkets",
    domain: "tools.filefree.ai",
    description:
      "Simple financial calculators, converters, and generators. Free forever.",
    gradient: "from-amber-500 to-orange-600",
    status: "Coming soon",
  },
];

const team = [
  {
    name: "Sankalp Sharma",
    role: "Founder — Product & Engineering",
  },
  {
    name: "Olga Sharma",
    role: "Co-founder — Partnerships & Revenue",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-border/40">
        <div className="mx-auto max-w-5xl px-6 py-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-zinc-700 flex items-center justify-center">
              <span className="text-sm font-bold text-white">P</span>
            </div>
            <span className="text-lg font-semibold tracking-tight">
              Paperwork Labs
            </span>
          </div>
          <a
            href="mailto:hello@paperworklabs.com"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            hello@paperworklabs.com
          </a>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-5xl px-6 py-24 md:py-32">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight leading-tight">
            We build tools that
            <br />
            eliminate paperwork.
          </h1>
          <p className="mt-6 text-lg text-muted-foreground max-w-2xl">
            Tax filing, LLC formation, compliance automation — the stuff nobody
            wants to do. We automate it so you never have to think about it
            again. Consumer products are free forever.
          </p>
          <a
            href="/admin"
            className="mt-8 inline-flex rounded-md border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-medium text-zinc-100 hover:bg-zinc-800"
          >
            Open Command Center
          </a>
        </section>

        <section className="mx-auto max-w-5xl px-6 pb-24">
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-widest mb-8">
            Products
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {products.map((product) => (
              <a
                key={product.name}
                href={`https://${product.domain}`}
                target="_blank"
                rel="noopener noreferrer"
                className="group rounded-xl border border-border/60 bg-card p-6 transition-all hover:border-border hover:bg-card/80"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-xl font-semibold flex items-center gap-2">
                      <span
                        className={`inline-block h-2.5 w-2.5 rounded-full bg-gradient-to-r ${product.gradient}`}
                      />
                      {product.name}
                    </h3>
                    <p className="mt-1 text-sm text-muted-foreground font-mono">
                      {product.domain}
                    </p>
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <p className="mt-4 text-sm text-muted-foreground leading-relaxed">
                  {product.description}
                </p>
                <p className="mt-3 text-xs text-muted-foreground/60">
                  {product.status}
                </p>
              </a>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-5xl px-6 pb-24">
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-widest mb-8">
            Team
          </h2>
          <div className="flex flex-col gap-4 sm:flex-row sm:gap-8">
            {team.map((person) => (
              <div key={person.name}>
                <p className="font-medium">{person.name}</p>
                <p className="text-sm text-muted-foreground">{person.role}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-border/40">
        <div className="mx-auto max-w-5xl px-6 py-8 flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-center">
          <p className="text-xs text-muted-foreground">
            Paperwork Labs LLC | California
          </p>
          <p className="text-xs text-muted-foreground">
            FileFree, LaunchFree, Distill, and Trinkets are products of
            Paperwork Labs LLC
          </p>
        </div>
      </footer>
    </div>
  );
}
