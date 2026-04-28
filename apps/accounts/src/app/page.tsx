import Link from "next/link";
import { formatSiblingExplainer } from "@paperwork-labs/auth-clerk/products";

export default function AccountsHomePage() {
  const siblingLine = formatSiblingExplainer();

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-20 text-slate-50">
      <div className="mx-auto max-w-3xl">
        <p className="text-sm font-medium uppercase tracking-widest text-slate-400">
          Paperwork Labs
        </p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">
          Sign in to your Paperwork Labs account
        </h1>
        <p className="mt-6 text-lg text-slate-300">
          Use the same identity across consumer products and tools from Paperwork Labs.
        </p>
        <p className="mt-4 text-sm leading-relaxed text-slate-400">{siblingLine}</p>
        <div className="mt-10 flex flex-wrap gap-4">
          <Link
            href="/sign-in"
            className="inline-flex rounded-md bg-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-900 hover:bg-white"
          >
            Sign in
          </Link>
          <Link
            href="/sign-up"
            className="inline-flex rounded-md border border-slate-600 bg-transparent px-4 py-2.5 text-sm font-semibold text-slate-100 hover:border-slate-400 hover:bg-slate-900/50"
          >
            Create account
          </Link>
        </div>
      </div>
    </main>
  );
}
