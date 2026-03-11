"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Camera, Upload, Loader2, AlertCircle } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import axios from "axios";

import { Button } from "@/components/ui/button";
import { DocumentCamera } from "@/components/camera/document-camera";
import { FileUploadZone } from "@/components/upload/file-upload-zone";
import { CurrencyDisplay } from "@/components/shared/currency-display";
import { checkImageQuality, getQualityMessage } from "@/lib/image-quality";
import { trackEvent } from "@/lib/posthog";
import { estimateRefund } from "@/lib/tax-estimator";
import { formatCurrency } from "@/lib/utils";
import api from "@/lib/api";

interface W2Fields {
  employer_name: string;
  employer_ein: string;
  employer_address: string;
  employee_name: string;
  employee_address: string;
  ssn_last_four: string;
  wages: number;
  federal_tax_withheld: number;
  social_security_wages: number;
  social_security_tax: number;
  medicare_wages: number;
  medicare_tax: number;
  state: string;
  state_wages: number;
  state_tax_withheld: number;
}

interface ExtractionResponse {
  fields: W2Fields;
  confidence: number;
  tier_used: string;
}

type DemoStep = "choose" | "camera" | "processing" | "result" | "error" | "rate-limited";

const fieldLabels: { key: keyof W2Fields; label: string; isCurrency: boolean }[] = [
  { key: "employer_name", label: "Employer", isCurrency: false },
  { key: "employee_name", label: "Your Name", isCurrency: false },
  { key: "wages", label: "Box 1 — Wages", isCurrency: true },
  { key: "federal_tax_withheld", label: "Box 2 — Federal Tax Withheld", isCurrency: true },
  { key: "social_security_wages", label: "Box 3 — Social Security Wages", isCurrency: true },
  { key: "medicare_wages", label: "Box 5 — Medicare Wages", isCurrency: true },
  { key: "state", label: "State", isCurrency: false },
  { key: "state_wages", label: "Box 16 — State Wages", isCurrency: true },
  { key: "state_tax_withheld", label: "Box 17 — State Tax Withheld", isCurrency: true },
];

export default function DemoPage() {
  const [step, setStep] = useState<DemoStep>("choose");
  const [result, setResult] = useState<ExtractionResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const processFile = useCallback(async (file: File) => {
    setStep("processing");
    trackEvent("demo_upload_started");

    const quality = await checkImageQuality(file);
    const qualityMsg = getQualityMessage(quality);
    if (qualityMsg) {
      toast.info(qualityMsg);
    }
    trackEvent("demo_image_quality", {
      blur_score: quality.blur.score,
      blur_passed: quality.blur.passed,
      dimensions_passed: quality.dimensions.passed,
      overall_passed: quality.passed,
    });

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await api.post("/api/v1/documents/demo-upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const data = response.data.data as ExtractionResponse;
      setResult(data);
      setStep("result");

      if (data.fields.wages > 0) {
        sessionStorage.setItem("filefree_demo_data", JSON.stringify(data));
      }

      trackEvent("demo_upload_success", {
        confidence: data.confidence,
        tier: data.tier_used,
        has_employer: !!data.fields.employer_name,
      });
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 429) {
        setStep("rate-limited");
        trackEvent("demo_rate_limited");
        return;
      }

      const message = err instanceof Error ? err.message : "Something went wrong";
      setErrorMsg(message);
      setStep("error");
      trackEvent("demo_upload_error", { error: message });
    }
  }, []);

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-2xl px-4 py-12">
        <Link
          href="/"
          className="mb-8 inline-block text-sm text-muted-foreground transition hover:text-foreground"
        >
          &larr; Back to FileFree
        </Link>

        <AnimatePresence mode="wait">
          {step === "choose" && <ChooseStep onCamera={() => setStep("camera")} onFile={processFile} />}
          {step === "camera" && <DocumentCamera onCapture={processFile} onClose={() => setStep("choose")} />}
          {step === "processing" && <ProcessingStep />}
          {step === "result" && result && <ResultStep data={result} onRetry={() => setStep("choose")} />}
          {step === "error" && <ErrorStep message={errorMsg} onRetry={() => setStep("choose")} />}
          {step === "rate-limited" && <RateLimitStep />}
        </AnimatePresence>
      </div>
    </main>
  );
}

function ChooseStep({ onCamera, onFile }: { onCamera: () => void; onFile: (f: File) => void }) {
  return (
    <motion.div
      key="choose"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
    >
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
        See it in{" "}
        <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
          action
        </span>
      </h1>
      <p className="mt-3 text-muted-foreground">
        Snap or upload your W-2 — no account needed. We&apos;ll extract every
        field in seconds.
      </p>

      <div className="mt-8 flex flex-col gap-4 sm:flex-row">
        <Button
          size="lg"
          className="h-14 flex-1 bg-gradient-to-r from-violet-600 to-purple-600 text-base font-semibold hover:from-violet-500 hover:to-purple-500"
          onClick={onCamera}
        >
          <Camera className="mr-2 h-5 w-5" />
          Open Camera
        </Button>
      </div>

      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border/50" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-background px-3 text-xs text-muted-foreground">or upload a photo</span>
        </div>
      </div>

      <FileUploadZone onFileAccepted={onFile} />

      <p className="mt-6 text-center text-xs text-muted-foreground/60">
        Your image is processed in memory and never stored. SSN is extracted
        locally and never sent to any AI service.
      </p>
    </motion.div>
  );
}

function ProcessingStep() {
  return (
    <motion.div
      key="processing"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="flex flex-col items-center py-20"
    >
      <div className="relative">
        <div className="h-20 w-20 animate-pulse rounded-full bg-gradient-to-r from-violet-500 to-purple-600 opacity-20 blur-xl" />
        <div className="absolute inset-0 flex items-center justify-center">
          <Loader2 className="h-10 w-10 animate-spin text-violet-500" />
        </div>
      </div>
      <p className="mt-6 text-lg font-medium text-foreground">Reading your W-2...</p>
      <p className="mt-2 text-sm text-muted-foreground">
        Our AI is extracting every field. This takes a few seconds.
      </p>
    </motion.div>
  );
}

function ResultStep({ data, onRetry }: { data: ExtractionResponse; onRetry: () => void }) {
  const visibleFields = fieldLabels.filter(({ key }) => {
    const val = data.fields[key];
    return typeof val === "string" ? val.length > 0 : val > 0;
  });

  const showEstimate = data.confidence >= 0.8 && data.fields.wages > 0;

  const estimate = showEstimate
    ? estimateRefund(data.fields.wages, data.fields.federal_tax_withheld)
    : null;

  const isRefund = estimate ? estimate.refundAmount > 0 : false;
  const estimateAmount = estimate
    ? isRefund
      ? estimate.refundAmount
      : estimate.owedAmount
    : 0;

  return (
    <motion.div
      key="result"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
        We found{" "}
        <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
          everything
        </span>
      </h2>
      <p className="mt-2 text-muted-foreground">
        Here&apos;s what we extracted from your W-2. Review it below.
      </p>

      {estimate && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3, duration: 0.5, ease: "easeOut" }}
          className={`mt-8 rounded-xl border p-6 text-center ${
            isRefund
              ? "border-green-500/30 bg-green-500/5"
              : "border-amber-500/30 bg-amber-500/5"
          }`}
        >
          <p className="text-sm font-medium text-muted-foreground">
            {isRefund ? "Estimated Federal Refund" : "Estimated Federal Amount Owed"}
          </p>
          <div className="mt-2">
            <CurrencyDisplay
              cents={estimateAmount}
              animate
              duration={1500}
              className={`text-4xl font-bold sm:text-5xl ${
                isRefund ? "text-green-400" : "text-amber-400"
              }`}
            />
          </div>
          <p className="mt-3 text-xs text-muted-foreground/70">
            Estimate assumes single filer with standard deduction.
            Sign up for your exact calculation with all filing statuses and credits.
          </p>
        </motion.div>
      )}

      <div className="mt-8 space-y-1 overflow-hidden rounded-xl border border-border/50">
        {visibleFields.map(({ key, label, isCurrency }, i) => {
          const value = data.fields[key];
          const display = isCurrency
            ? formatCurrency(value as number)
            : String(value);

          return (
            <motion.div
              key={key}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.6 + i * 0.06, duration: 0.25, ease: "easeOut" }}
              className="flex items-center justify-between bg-card/30 px-4 py-3 text-sm"
            >
              <span className="text-muted-foreground">{label}</span>
              <span className="font-medium text-foreground">{display}</span>
            </motion.div>
          );
        })}
      </div>

      {data.fields.ssn_last_four && (
        <p className="mt-3 text-xs text-muted-foreground/60">
          SSN ending in {data.fields.ssn_last_four} detected and secured.
        </p>
      )}

      <div className="mt-8 rounded-xl border border-violet-500/30 bg-violet-500/5 p-6">
        <h3 className="text-lg font-semibold text-foreground">
          {estimate && isRefund
            ? `Get your ${formatCurrency(estimate.refundAmount)} refund`
            : "Ready to file your return?"}
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          {estimate && isRefund
            ? "Create a free account to file and claim your refund."
            : "Create a free account to save your data and get your completed return."}
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <Button
            asChild
            className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500"
          >
            <Link href="/auth/register">
              Create Free Account
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button variant="outline" onClick={onRetry}>
            <Upload className="mr-2 h-4 w-4" />
            Try Another W-2
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

function ErrorStep({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <motion.div
      key="error"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="flex flex-col items-center py-16"
    >
      <div className="rounded-full bg-destructive/10 p-4">
        <AlertCircle className="h-8 w-8 text-destructive" />
      </div>
      <h2 className="mt-4 text-xl font-semibold text-foreground">
        Couldn&apos;t read that W-2
      </h2>
      <p className="mt-2 max-w-md text-center text-sm text-muted-foreground">
        {message || "Try taking another photo with better lighting, or upload a clearer image."}
      </p>
      <Button className="mt-6" onClick={onRetry}>
        Try Again
      </Button>
    </motion.div>
  );
}

function RateLimitStep() {
  return (
    <motion.div
      key="rate-limited"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="flex flex-col items-center py-16"
    >
      <div className="rounded-full bg-violet-500/10 p-4">
        <Upload className="h-8 w-8 text-violet-400" />
      </div>
      <h2 className="mt-4 text-xl font-semibold text-foreground">
        You&apos;ve used your free scans for today
      </h2>
      <p className="mt-2 max-w-md text-center text-sm text-muted-foreground">
        Create a free account to scan more W-2s and file your return — completely free.
      </p>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <Button
          asChild
          className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500"
        >
          <Link href="/auth/register">
            Create Free Account
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </div>
      <p className="mt-4 text-xs text-muted-foreground/60">
        Free forever. No credit card required. File federal + state for $0.
      </p>
    </motion.div>
  );
}
