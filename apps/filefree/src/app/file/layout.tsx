"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { X, Check } from "lucide-react";
import { motion } from "framer-motion";

import { FILING_STEPS, useFilingStore } from "@/stores/filing-store";

export default function FileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { currentStep, reset } = useFilingStore();

  const activeIndex = FILING_STEPS.findIndex((s) => pathname.startsWith(s.path));
  const displayStep = activeIndex >= 0 ? activeIndex : currentStep;
  const progress = ((displayStep + 1) / FILING_STEPS.length) * 100;

  if (pathname === "/file") return <>{children}</>;

  return (
    <div className="min-h-screen bg-background">
      <div className="sticky top-14 z-40 border-b border-border/40 bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <div className="flex items-center gap-6">
            {FILING_STEPS.map((step, i) => {
              const isComplete = i < displayStep;
              const isActive = i === displayStep;
              return (
                <button
                  key={step.key}
                  onClick={() => {
                    if (isComplete) router.push(step.path);
                  }}
                  disabled={!isComplete}
                  className={`flex items-center gap-1.5 text-sm transition ${
                    isActive
                      ? "font-semibold text-foreground"
                      : isComplete
                        ? "text-violet-400 hover:text-violet-300 cursor-pointer"
                        : "text-muted-foreground/50 cursor-default"
                  }`}
                >
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
                      isActive
                        ? "bg-violet-600 text-white"
                        : isComplete
                          ? "bg-violet-600/20 text-violet-400"
                          : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {isComplete ? <Check className="h-3.5 w-3.5" /> : i + 1}
                  </span>
                  <span className="hidden sm:inline">{step.label}</span>
                </button>
              );
            })}
          </div>

          <Link
            href="/"
            onClick={() => reset()}
            className="text-muted-foreground hover:text-foreground transition"
            aria-label="Exit filing"
          >
            <X className="h-5 w-5" />
          </Link>
        </div>

        <div className="h-0.5 bg-muted">
          <motion.div
            className="h-full bg-gradient-to-r from-violet-600 to-purple-600"
            initial={false}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.4, ease: "easeInOut" }}
          />
        </div>
      </div>

      <div className="mx-auto max-w-3xl px-4 py-8">{children}</div>
    </div>
  );
}
