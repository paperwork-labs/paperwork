"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Download, Share2, ArrowDown, ArrowUp } from "lucide-react";

import { Button, Card, CardContent, CardHeader, CardTitle } from "@venture/ui";
import { useFilingStore } from "@/stores/filing-store";
import { useCalculation, useCalculateTax } from "@/hooks/use-tax";
import { trackEvent } from "@/lib/posthog";
import { slideInUp, staggerContainer } from "@/lib/motion";

function formatCents(cents: number): string {
  return `$${(cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function AnimatedAmount({
  cents,
  isRefund,
}: {
  cents: number;
  isRefund: boolean;
}) {
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    const target = cents;
    const duration = 1500;
    const steps = 60;
    const increment = target / steps;
    let current = 0;
    let step = 0;

    const interval = setInterval(() => {
      step++;
      current = Math.min(Math.round(increment * step), target);
      setDisplayed(current);
      if (step >= steps) clearInterval(interval);
    }, duration / steps);

    return () => clearInterval(interval);
  }, [cents]);

  return (
    <span
      className={`text-5xl font-bold tracking-tight sm:text-6xl ${
        isRefund
          ? "bg-gradient-to-r from-green-400 to-emerald-500 bg-clip-text text-transparent"
          : "text-amber-400"
      }`}
    >
      {formatCents(displayed)}
    </span>
  );
}

export default function SummaryPage() {
  const { filingId, w2s } = useFilingStore();
  const calculateTax = useCalculateTax();
  const { data: calc } = useCalculation(filingId);

  useEffect(() => {
    if (filingId && !calc) {
      calculateTax.mutate(filingId, {
        onSuccess: (data) => {
          trackEvent("tax_calculated", {
            refund: data.refund_amount,
            owed: data.owed_amount,
          });
        },
      });
    }
  }, [filingId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!calc && calculateTax.isPending) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center">
        <div className="h-16 w-16 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 animate-pulse" />
        <p className="mt-4 text-sm text-muted-foreground animate-pulse">
          Calculating your return...
        </p>
      </div>
    );
  }

  if (!calc) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
        <p className="text-muted-foreground">
          No calculation available. Please complete the previous steps.
        </p>
      </div>
    );
  }

  const isRefund = calc.refund_amount > 0;
  const mainAmount = isRefund ? calc.refund_amount : calc.owed_amount;

  return (
    <motion.div
      className="space-y-6"
      initial="hidden"
      animate="visible"
      variants={staggerContainer}
    >
      {/* Refund/Owed reveal */}
      <motion.div
        className="flex flex-col items-center py-8 text-center"
        variants={slideInUp}
      >
        <div
          className={`flex h-12 w-12 items-center justify-center rounded-full ${
            isRefund ? "bg-green-500/20" : "bg-amber-500/20"
          }`}
        >
          {isRefund ? (
            <ArrowDown className="h-6 w-6 text-green-400" />
          ) : (
            <ArrowUp className="h-6 w-6 text-amber-400" />
          )}
        </div>
        <p className="mt-3 text-sm font-medium text-muted-foreground">
          {isRefund ? "Your estimated refund" : "Estimated amount owed"}
        </p>
        <div className="mt-2">
          <AnimatedAmount cents={mainAmount} isRefund={isRefund} />
        </div>
      </motion.div>

      {/* Breakdown */}
      <motion.div variants={slideInUp}>
        <Card className="border-border/50">
          <CardHeader>
            <CardTitle className="text-base">Return Breakdown</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <BreakdownRow
              label="Adjusted Gross Income"
              value={formatCents(calc.adjusted_gross_income)}
            />
            <BreakdownRow
              label="Standard Deduction"
              value={`-${formatCents(calc.standard_deduction)}`}
              muted
            />
            <BreakdownRow
              label="Taxable Income"
              value={formatCents(calc.taxable_income)}
            />
            <div className="border-t border-border/30 pt-3">
              <BreakdownRow
                label="Federal Tax"
                value={formatCents(calc.federal_tax)}
              />
              {calc.state_tax > 0 && (
                <BreakdownRow
                  label="State Tax"
                  value={formatCents(calc.state_tax)}
                />
              )}
              <BreakdownRow
                label="Total Withheld"
                value={formatCents(calc.total_withheld)}
                highlight
              />
            </div>
            <div className="border-t border-border/30 pt-3">
              <BreakdownRow
                label={isRefund ? "Your Refund" : "Amount Owed"}
                value={formatCents(mainAmount)}
                bold
                highlight={isRefund}
              />
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Actions */}
      <motion.div className="flex flex-col gap-3 sm:flex-row" variants={slideInUp}>
        <Button
          className="flex-1 h-12 bg-gradient-to-r from-violet-600 to-purple-600 text-white border-0 hover:from-violet-500 hover:to-purple-500 text-base font-semibold"
          disabled
        >
          <Download className="mr-2 h-4 w-4" />
          Download PDF (Coming Soon)
        </Button>
        <Button variant="outline" className="flex-1 h-12" disabled>
          <Share2 className="mr-2 h-4 w-4" />
          Share Tax Receipt
        </Button>
      </motion.div>

      <motion.p
        className="text-center text-xs text-muted-foreground"
        variants={slideInUp}
      >
        This is an estimate based on the information you provided. Actual
        results may vary. Not tax advice.
      </motion.p>
    </motion.div>
  );
}

function BreakdownRow({
  label,
  value,
  muted,
  bold,
  highlight,
}: {
  label: string;
  value: string;
  muted?: boolean;
  bold?: boolean;
  highlight?: boolean;
}) {
  return (
    <div className="flex justify-between text-sm">
      <span className={muted ? "text-muted-foreground" : "text-foreground"}>
        {label}
      </span>
      <span
        className={`font-mono ${
          bold
            ? "font-bold text-foreground"
            : highlight
              ? "font-medium text-green-400"
              : "text-foreground"
        }`}
      >
        {value}
      </span>
    </div>
  );
}
