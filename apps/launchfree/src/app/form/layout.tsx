"use client";

import Link from "next/link";
import { useFormationStore, WIZARD_STEPS, type WizardStep } from "@/lib/stores/formation";
import { cn, Progress } from "@paperwork-labs/ui";
import { ArrowLeft, Check, Building2 } from "lucide-react";

const STEP_LABELS: Record<WizardStep, string> = {
  state: "State",
  name: "Business Name",
  details: "Details",
  agent: "Registered Agent",
  address: "Address",
  members: "Members",
  review: "Review",
};

export default function FormationWizardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { currentStep } = useFormationStore();
  const currentIndex = WIZARD_STEPS.indexOf(currentStep);
  const progress = ((currentIndex + 1) / WIZARD_STEPS.length) * 100;

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4">
          <Link
            href="/"
            className="flex items-center gap-2 text-slate-400 transition-colors hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="text-sm">Back</span>
          </Link>

          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-cyan-400" />
            <span className="font-semibold text-white">LaunchFree</span>
          </div>

          <div className="w-16" />
        </div>

        <div className="mx-auto max-w-4xl px-4 pb-4">
          <Progress value={progress} className="h-1" />
          <div className="mt-4 flex justify-between">
            {WIZARD_STEPS.map((step, index) => {
              const isActive = step === currentStep;
              const isCompleted = index < currentIndex;
              const isPast = index <= currentIndex;

              return (
                <div
                  key={step}
                  className={cn(
                    "flex flex-col items-center gap-1",
                    isActive && "text-cyan-400",
                    isCompleted && "text-cyan-500",
                    !isPast && "text-slate-600"
                  )}
                >
                  <div
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-full border-2 text-xs font-medium transition-colors",
                      isActive && "border-cyan-400 bg-cyan-400/20 text-cyan-400",
                      isCompleted && "border-cyan-500 bg-cyan-500 text-slate-950",
                      !isPast && "border-slate-700 text-slate-600"
                    )}
                  >
                    {isCompleted ? <Check className="h-4 w-4" /> : index + 1}
                  </div>
                  <span className="hidden text-xs sm:block">
                    {STEP_LABELS[step]}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-8">{children}</main>
    </div>
  );
}
