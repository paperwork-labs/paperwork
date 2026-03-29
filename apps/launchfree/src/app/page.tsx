import Link from "next/link";
import { ArrowRight, Building2, Shield, Zap } from "lucide-react";

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

        <Link
          href="/form"
          className="mt-10 inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-teal-400 to-cyan-500 px-8 py-4 text-lg font-semibold text-slate-950 transition-all hover:from-teal-300 hover:to-cyan-400 hover:shadow-lg hover:shadow-cyan-500/25"
        >
          Start Your LLC
          <ArrowRight className="h-5 w-5" />
        </Link>

        <div className="mt-16 grid gap-6 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
            <Zap className="h-8 w-8 text-cyan-400" />
            <h3 className="mt-4 font-semibold text-white">5 Minutes</h3>
            <p className="mt-2 text-sm text-slate-400">
              Answer a few questions and we handle the rest.
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
            <Building2 className="h-8 w-8 text-cyan-400" />
            <h3 className="mt-4 font-semibold text-white">All 50 States</h3>
            <p className="mt-2 text-sm text-slate-400">
              Form your LLC in any state. We file directly with the Secretary of State.
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
            <Shield className="h-8 w-8 text-cyan-400" />
            <h3 className="mt-4 font-semibold text-white">Free Forever</h3>
            <p className="mt-2 text-sm text-slate-400">
              No hidden fees. You only pay the state filing fee.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
