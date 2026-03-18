import Link from "next/link";

export default function DistillHomePage() {
  return (
    <main className="min-h-screen bg-slate-900 px-6 py-20 text-slate-50">
      <div className="mx-auto max-w-3xl">
        <p className="text-sm font-medium uppercase tracking-widest text-blue-300">
          Distill
        </p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">
          Compliance automation for modern platforms.
        </h1>
        <p className="mt-6 text-lg text-slate-300">
          Distill turns raw financial documents into structured, actionable data
          for CPA firms and embedded-finance products.
        </p>
        <Link
          href="/dashboard"
          className="mt-8 inline-flex rounded-md border border-blue-700/50 bg-blue-900/30 px-4 py-2 text-sm font-medium text-blue-100 hover:bg-blue-900/50"
        >
          Open dashboard placeholder
        </Link>
      </div>
    </main>
  );
}
