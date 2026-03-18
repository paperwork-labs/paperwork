"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { CheckCircle, AlertTriangle } from "lucide-react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label } from "@paperwork-labs/ui";
import { useFilingStore } from "@/stores/filing-store";
import { useConfirmData } from "@/hooks/use-filing";
import { trackEvent } from "@/lib/posthog";
import { slideInUp, staggerContainer } from "@/lib/motion";

function formatCents(cents: number): string {
  return `$${(cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
}

function ConfidenceBadge({ score }: { score: number }) {
  if (score >= 0.9)
    return (
      <span className="flex items-center gap-1 text-xs text-green-400">
        <CheckCircle className="h-3 w-3" /> High confidence
      </span>
    );
  if (score >= 0.7)
    return (
      <span className="flex items-center gap-1 text-xs text-yellow-400">
        <AlertTriangle className="h-3 w-3" /> Review recommended
      </span>
    );
  return (
    <span className="flex items-center gap-1 text-xs text-red-400">
      <AlertTriangle className="h-3 w-3" /> Please verify
    </span>
  );
}

export default function ConfirmPage() {
  const router = useRouter();
  const { w2s, updateW2, filingId, setCurrentStep } = useFilingStore();
  const confirmData = useConfirmData();

  useEffect(() => {
    if (w2s.length === 0) router.replace("/file/w2");
  }, [w2s.length, router]);

  if (w2s.length === 0) return null;

  function handleConfirm() {
    trackEvent("filing_step_completed", { step: "confirm" });
    if (filingId) {
      confirmData.mutate(filingId, {
        onSuccess: () => {
          setCurrentStep(2);
          router.push("/file/details");
        },
      });
    } else {
      setCurrentStep(2);
      router.push("/file/details");
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
        <h2 className="text-2xl font-bold text-foreground">
          Review your information
        </h2>
        <p className="mt-1 text-muted-foreground">
          Make sure everything looks correct. You can edit any field below.
        </p>
      </motion.div>

      {w2s.length > 0 && (
        <motion.div variants={slideInUp}>
          <Card className="border-border/50">
            <CardHeader>
              <CardTitle className="text-base">Your Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="employee_name">Full Name</Label>
                  <Input
                    id="employee_name"
                    value={w2s[0].employee_name}
                    onChange={(e) =>
                      updateW2(0, { employee_name: e.target.value })
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="ssn">SSN</Label>
                  <Input
                    id="ssn"
                    value={`XXX-XX-${w2s[0].ssn_last_four || "????"}`}
                    disabled
                    className="opacity-60"
                  />
                </div>
                <div className="sm:col-span-2">
                  <Label htmlFor="employee_address">Address</Label>
                  <Input
                    id="employee_address"
                    value={w2s[0].employee_address}
                    onChange={(e) =>
                      updateW2(0, { employee_address: e.target.value })
                    }
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {w2s.map((w2, index) => (
        <motion.div key={index} variants={slideInUp}>
          <Card className="border-border/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">
                {w2.employer_name || `W-2 #${index + 1}`}
              </CardTitle>
              {w2.confidence !== undefined && (
                <ConfidenceBadge score={w2.confidence} />
              )}
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                <EditableField
                  label="Employer Name"
                  value={w2.employer_name}
                  onChange={(v) => updateW2(index, { employer_name: v })}
                />
                <EditableField
                  label="EIN"
                  value={w2.employer_ein}
                  onChange={(v) => updateW2(index, { employer_ein: v })}
                />
                <CentsField
                  label="Wages (Box 1)"
                  cents={w2.wages}
                  onChange={(v) => updateW2(index, { wages: v })}
                />
                <CentsField
                  label="Federal Withheld (Box 2)"
                  cents={w2.federal_tax_withheld}
                  onChange={(v) =>
                    updateW2(index, { federal_tax_withheld: v })
                  }
                />
                <CentsField
                  label="SS Wages (Box 3)"
                  cents={w2.social_security_wages}
                  onChange={(v) =>
                    updateW2(index, { social_security_wages: v })
                  }
                />
                <CentsField
                  label="SS Tax (Box 4)"
                  cents={w2.social_security_tax}
                  onChange={(v) =>
                    updateW2(index, { social_security_tax: v })
                  }
                />
                <CentsField
                  label="Medicare Wages (Box 5)"
                  cents={w2.medicare_wages}
                  onChange={(v) => updateW2(index, { medicare_wages: v })}
                />
                <CentsField
                  label="Medicare Tax (Box 6)"
                  cents={w2.medicare_tax}
                  onChange={(v) => updateW2(index, { medicare_tax: v })}
                />
                {w2.state && (
                  <>
                    <EditableField
                      label="State"
                      value={w2.state}
                      onChange={(v) => updateW2(index, { state: v })}
                    />
                    <CentsField
                      label="State Withheld (Box 17)"
                      cents={w2.state_tax_withheld}
                      onChange={(v) =>
                        updateW2(index, { state_tax_withheld: v })
                      }
                    />
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      ))}

      <motion.div variants={slideInUp}>
        <Button
          onClick={handleConfirm}
          disabled={confirmData.isPending}
          className="w-full h-12 bg-gradient-to-r from-violet-600 to-purple-600 text-white border-0 hover:from-violet-500 hover:to-purple-500 text-base font-semibold"
        >
          {confirmData.isPending
            ? "Saving..."
            : "Everything Looks Right"}
        </Button>
      </motion.div>
    </motion.div>
  );
}

function EditableField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1"
      />
    </div>
  );
}

function CentsField({
  label,
  cents,
  onChange,
}: {
  label: string;
  cents: number;
  onChange: (v: number) => void;
}) {
  const displayValue = (cents / 100).toFixed(2);

  return (
    <div>
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <div className="relative mt-1">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
          $
        </span>
        <Input
          type="number"
          step="0.01"
          value={displayValue}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === "") { onChange(0); return; }
            const val = parseFloat(raw);
            if (!isNaN(val)) onChange(Math.round(val * 100));
          }}
          className="pl-7"
        />
      </div>
    </div>
  );
}
