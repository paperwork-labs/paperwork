import Link from "next/link";
import { PaperclipMark } from "@/components/PaperclipMark";

const PRODUCTS = [
  "FileFree",
  "LaunchFree",
  "AxiomFolio",
  "Distill",
  "Trinkets",
] as const;

const PROMPTS_DOC =
  "https://github.com/paperwork-labs/paperwork/blob/main/docs/brand/PROMPTS.md";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-lg flex-col justify-center px-6 py-16">
      <div className="flex flex-col items-center text-center">
        <Link
          href={PROMPTS_DOC}
          target="_blank"
          rel="noopener noreferrer"
          className="group mb-6 block rounded-2xl p-4 ring-1 ring-slate-700/60 transition hover:ring-amber-500/40"
          title="Paperwork Labs parent mark prompt (paperclip) — docs/brand/PROMPTS.md"
        >
          <PaperclipMark className="h-20 w-20 transition group-hover:opacity-95" />
          <span className="mt-2 block text-xs font-medium text-slate-400 group-hover:text-amber-400/90">
            Placeholder mark · see PROMPTS.md
          </span>
        </Link>

        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
          Identity
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-[#F8FAFC]">
          Paperwork ID
        </h1>
        <p className="mt-1 text-sm text-slate-400">by Paperwork Labs</p>

        <p className="mt-8 max-w-md text-pretty text-sm leading-relaxed text-slate-300">
          Your Paperwork ID is the single sign-on identity across our products.
          Sign in or create an account once — then use the same account on each
          app without registering again.
        </p>

        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {PRODUCTS.map((name) => (
            <span
              key={name}
              className="rounded-full border border-slate-600/80 bg-slate-900/50 px-3 py-1 text-xs font-medium text-slate-200"
            >
              {name}
            </span>
          ))}
        </div>

        <div className="mt-10 flex flex-wrap justify-center gap-4 text-sm font-medium">
          <Link
            href="/sign-in"
            className="rounded-lg bg-amber-500 px-5 py-2.5 text-[#0F172A] transition hover:bg-amber-400"
          >
            Sign in
          </Link>
          <Link
            href="/sign-up"
            className="rounded-lg border border-slate-500 px-5 py-2.5 text-[#F8FAFC] transition hover:border-amber-500/50 hover:text-amber-100"
          >
            Create account
          </Link>
        </div>
      </div>
    </main>
  );
}
