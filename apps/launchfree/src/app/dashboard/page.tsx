import type { Metadata } from "next";
import Link from "next/link";
import { PlusCircle, Sparkles } from "lucide-react";
import { Button, Card, CardContent } from "@paperwork-labs/ui";
import { getUserFormations } from "@/lib/dashboard-formations";
import { FormationCard } from "./components/formation-card";

export const metadata: Metadata = {
  title: "Dashboard — LaunchFree",
  description: "Track your LLC formations and filings.",
};

export default async function DashboardPage() {
  const formations = await getUserFormations();

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8 flex flex-col gap-4 sm:mb-10 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-50 sm:text-3xl">
            Your LLCs
          </h1>
          <p className="mt-2 max-w-lg text-sm text-slate-400 sm:text-base">
            Formation status, filings, and next steps in one place.
          </p>
        </div>
        <Button
          asChild
          className="w-full shrink-0 bg-gradient-to-r from-teal-500 to-cyan-500 text-slate-950 shadow-lg shadow-teal-500/20 hover:from-teal-400 hover:to-cyan-400 sm:w-auto"
        >
          <Link href="/form" className="gap-2">
            <PlusCircle className="size-4" aria-hidden />
            Start new LLC
          </Link>
        </Button>
      </div>

      {formations.length === 0 ? (
        <Card className="border-slate-800 bg-slate-900/60">
            <CardContent className="flex flex-col items-center gap-6 px-6 py-14 text-center">
              <div className="flex size-14 items-center justify-center rounded-2xl bg-teal-500/10 ring-1 ring-teal-500/30">
                <Sparkles className="size-7 text-teal-400" aria-hidden />
              </div>
              <div className="max-w-sm space-y-2">
                <h2 className="text-lg font-semibold text-slate-100">
                  No formations yet
                </h2>
                <p className="text-sm leading-relaxed text-slate-400">
                  Start your first LLC in minutes — we handle the state filing
                  paperwork so you can focus on building.
                </p>
              </div>
              <Button
                asChild
                size="lg"
                className="bg-gradient-to-r from-teal-500 to-cyan-500 text-slate-950 hover:from-teal-400 hover:to-cyan-400"
              >
                <Link href="/form" className="gap-2">
                  <PlusCircle className="size-4" aria-hidden />
                  Start your LLC
                </Link>
              </Button>
            </CardContent>
          </Card>
      ) : (
        <ul className="flex flex-col gap-3 sm:gap-4">
          {formations.map((formation, index) => (
            <li key={formation.id}>
              <FormationCard formation={formation} index={index} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
