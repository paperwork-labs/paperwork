export default function LaunchFreeHomePage() {
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-20 text-slate-50">
      <div className="mx-auto max-w-3xl">
        <p className="text-sm font-medium uppercase tracking-widest text-cyan-300">
          LaunchFree
        </p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">
          Starting a business should not require a lawyer.
        </h1>
        <p className="mt-6 text-lg text-slate-300">
          Pick your state, answer a few questions, and we prepare your LLC filing.
          LaunchFree is free forever.
        </p>
        <div className="mt-10 rounded-xl border border-cyan-900/60 bg-slate-900/60 p-6">
          <p className="text-sm text-cyan-200">Scaffold complete</p>
          <p className="mt-2 text-sm text-slate-300">
            Next milestone: formation wizard and state-specific filing flow.
          </p>
        </div>
      </div>
    </main>
  );
}
