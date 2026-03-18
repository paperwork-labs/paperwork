const tools = [
  "Mortgage calculator",
  "Compound interest calculator",
  "Savings goal planner",
  "Budget planner",
];

export default function TrinketsHomePage() {
  return (
    <main className="min-h-screen bg-stone-950 px-6 py-20 text-amber-50">
      <div className="mx-auto max-w-3xl">
        <p className="text-sm font-medium uppercase tracking-widest text-amber-300">
          Trinkets
        </p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">
          Small tools. Big clarity.
        </h1>
        <p className="mt-6 text-lg text-amber-100/80">
          Free utility tools that help you make better financial decisions in
          minutes.
        </p>
        <ul className="mt-10 space-y-3">
          {tools.map((tool) => (
            <li
              key={tool}
              className="rounded-lg border border-amber-700/30 bg-stone-900/60 px-4 py-3 text-sm"
            >
              {tool}
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
