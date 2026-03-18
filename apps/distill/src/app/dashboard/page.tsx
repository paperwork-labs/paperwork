import { redirect } from "next/navigation";

export default function DistillDashboardPage() {
  const hasAccess =
    process.env.NODE_ENV === "development" ||
    process.env.DISTILL_DASHBOARD_ENABLED === "true";

  if (!hasAccess) {
    redirect("/");
  }

  return (
    <main className="min-h-screen bg-slate-900 px-6 py-20 text-slate-50">
      <div className="mx-auto max-w-3xl rounded-xl border border-slate-700 bg-slate-800/60 p-6">
        <h1 className="text-2xl font-semibold tracking-tight">
          Distill dashboard scaffold
        </h1>
        <p className="mt-3 text-sm text-slate-300">
          Multi-tenant onboarding, client queue, and export workflows land here
          in Phase 9.
        </p>
      </div>
    </main>
  );
}
