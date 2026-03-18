"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { User, Users, UserMinus, Home } from "lucide-react";

import { Button } from "@paperwork-labs/ui";
import { useFilingStore } from "@/stores/filing-store";
import { useUpdateFiling } from "@/hooks/use-filing";
import { trackEvent } from "@/lib/posthog";
import { slideInUp, staggerContainer } from "@/lib/motion";

const FILING_STATUSES = [
  {
    value: "single",
    label: "Single",
    description: "Unmarried or legally separated",
    icon: User,
  },
  {
    value: "married_joint",
    label: "Married Filing Jointly",
    description: "Married and filing one return together",
    icon: Users,
  },
  {
    value: "married_separate",
    label: "Married Filing Separately",
    description: "Married but filing your own return",
    icon: UserMinus,
  },
  {
    value: "head_of_household",
    label: "Head of Household",
    description: "Unmarried and paying 50%+ of household costs",
    icon: Home,
  },
] as const;

export default function DetailsPage() {
  const router = useRouter();
  const { filingId, filingStatusType, setFilingStatusType, setCurrentStep } =
    useFilingStore();
  const updateFiling = useUpdateFiling();

  function handleSelect(value: string) {
    setFilingStatusType(value);
  }

  function handleContinue() {
    if (!filingStatusType) return;
    trackEvent("filing_step_completed", { step: "details", filing_status: filingStatusType });

    if (filingId) {
      updateFiling.mutate(
        { filingId, filing_status_type: filingStatusType },
        {
          onSuccess: () => {
            setCurrentStep(3);
            router.push("/file/summary");
          },
        }
      );
    } else {
      setCurrentStep(3);
      router.push("/file/summary");
    }
  }

  return (
    <motion.div
      className="space-y-6"
      initial="hidden"
      animate="visible"
      variants={staggerContainer}
    >
      <motion.div variants={slideInUp}>
        <h2 className="text-2xl font-bold text-foreground">Filing status</h2>
        <p className="mt-1 text-muted-foreground">
          Select the filing status that applies to you. This determines your
          standard deduction and tax brackets.
        </p>
      </motion.div>

      <div className="grid gap-3 sm:grid-cols-2">
        {FILING_STATUSES.map(({ value, label, description, icon: Icon }) => {
          const selected = filingStatusType === value;
          return (
            <motion.button
              key={value}
              variants={slideInUp}
              onClick={() => handleSelect(value)}
              className={`flex items-start gap-3 rounded-xl border p-4 text-left transition ${
                selected
                  ? "border-violet-500 bg-violet-500/10"
                  : "border-border/50 hover:border-border"
              }`}
            >
              <div
                className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                  selected
                    ? "bg-violet-600 text-white"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                <Icon className="h-5 w-5" />
              </div>
              <div>
                <p
                  className={`font-medium ${selected ? "text-foreground" : "text-foreground/80"}`}
                >
                  {label}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {description}
                </p>
              </div>
            </motion.button>
          );
        })}
      </div>

      <motion.div variants={slideInUp}>
        <Button
          onClick={handleContinue}
          disabled={!filingStatusType || updateFiling.isPending}
          className="w-full h-12 bg-gradient-to-r from-violet-600 to-purple-600 text-white border-0 hover:from-violet-500 hover:to-purple-500 text-base font-semibold"
        >
          {updateFiling.isPending ? "Saving..." : "Calculate My Return"}
        </Button>
      </motion.div>
    </motion.div>
  );
}
