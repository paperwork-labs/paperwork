"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Separator,
} from "@paperwork-labs/ui";
import {
  useFormationStore,
  type Address,
  type Member,
  type RegisteredAgent,
  type WizardStep,
} from "@/lib/stores/formation";
import { ArrowLeft, CheckCircle2, Loader2, Pencil } from "lucide-react";

/** State filing fees (USD) for supported formation states */
export const STATE_FEES: Record<string, number> = {
  CA: 70,
  TX: 300,
  FL: 125,
  DE: 90,
  WY: 100,
  NY: 200,
  NV: 425,
  IL: 150,
  GA: 100,
  WA: 180,
};

function formatAddress(addr: Address | undefined): string {
  if (!addr?.street1?.trim()) {
    return "—";
  }
  const lines: string[] = [addr.street1.trim()];
  if (addr.street2?.trim()) {
    lines.push(addr.street2.trim());
  }
  lines.push(
    `${addr.city?.trim() || ""}, ${addr.state?.trim() || ""} ${addr.zip?.trim() || ""}`.trim()
  );
  return lines.join("\n");
}

function formatCurrency(centsOrDollars: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(centsOrDollars);
}

function memberRoleLabel(role: Member["role"]): string {
  switch (role) {
    case "member":
      return "Member";
    case "manager":
      return "Manager";
    case "organizer":
      return "Organizer";
    default:
      return role;
  }
}

function managementLabel(type: "member" | "manager" | undefined): string {
  if (type === "manager") return "Manager-managed";
  if (type === "member") return "Member-managed";
  return "—";
}

function registeredAgentSummary(agent: RegisteredAgent): {
  headline: string;
  addressBlock: string;
} {
  if (agent.type === "launchfree") {
    return {
      headline: "LaunchFree registered agent",
      addressBlock: formatAddress(agent.address),
    };
  }
  if (agent.type === "self") {
    return {
      headline: agent.name?.trim() || "Yourself (member)",
      addressBlock: formatAddress(agent.address),
    };
  }
  return {
    headline: agent.name?.trim() || "Registered agent",
    addressBlock: formatAddress(agent.address),
  };
}

interface ReviewSectionProps {
  title: string;
  step: WizardStep;
  children: React.ReactNode;
}

function ReviewSection({ title, step, children }: ReviewSectionProps) {
  const setStep = useFormationStore((s) => s.setStep);

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {title}
        </p>
        <div className="text-sm text-slate-200">{children}</div>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-9 shrink-0 gap-1.5 text-cyan-400 hover:bg-slate-800 hover:text-cyan-300"
        onClick={() => setStep(step)}
      >
        <Pencil className="h-3.5 w-3.5" />
        Edit
      </Button>
    </div>
  );
}

/** Placeholder until formation API is wired */
async function placeholderSubmitFormation(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 1200));
}

export function ReviewStep() {
  const data = useFormationStore((s) => s.data);
  const prevStep = useFormationStore((s) => s.prevStep);
  const setSubmitting = useFormationStore((s) => s.setSubmitting);
  const setError = useFormationStore((s) => s.setError);
  const isSubmitting = useFormationStore((s) => s.isSubmitting);
  const submissionError = useFormationStore((s) => s.submissionError);

  const [submitted, setSubmitted] = useState(false);

  const stateCode = data.stateCode?.toUpperCase() ?? "";
  const filingFee =
    stateCode && STATE_FEES[stateCode] != null
      ? STATE_FEES[stateCode]
      : null;

  const businessDisplay = [data.businessName, data.nameSuffix]
    .filter(Boolean)
    .join(" ");

  const agent = data.registeredAgent;
  const agentSummary = agent
    ? registeredAgentSummary(agent)
    : { headline: "—", addressBlock: "—" };

  const mailingDifferent =
    !data.sameMailingAddress &&
    data.mailingAddress &&
    data.mailingAddress.street1?.trim();

  const handleSubmit = useCallback(async () => {
    setError(null);
    setSubmitting(true);
    try {
      await placeholderSubmitFormation();
      setSubmitted(true);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }, [setError, setSubmitting]);

  if (submitted) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            You&apos;re all set
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            We received your formation details. Next, we&apos;ll file with the
            state and keep you updated.
          </p>
        </div>

        <Card className="border-slate-800 bg-slate-900/50 text-white">
          <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-teal-500/20 text-teal-400">
              <CheckCircle2 className="h-8 w-8" />
            </div>
            <p className="text-lg font-semibold text-white">
              Submission successful
            </p>
            <p className="max-w-sm text-sm text-slate-400">
              This is a preview flow. When filing goes live, you&apos;ll get a
              confirmation email and filing reference here.
            </p>
          </CardContent>
        </Card>

        <Button
          type="button"
          variant="ghost"
          onClick={prevStep}
          className="text-slate-400 hover:text-white"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to review
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Review & submit
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Confirm everything looks correct before you submit your LLC formation.
        </p>
      </div>

      <Card className="border-slate-800 bg-slate-900/50 text-white">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg text-white">Summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <ReviewSection title="State & filing fee" step="state">
            <p className="font-medium text-white">
              {stateCode || "—"}
              {filingFee != null && (
                <span className="ml-2 font-normal text-slate-400">
                  · State filing fee {formatCurrency(filingFee)}
                </span>
              )}
              {stateCode && filingFee == null && (
                <span className="ml-2 font-normal text-slate-500">
                  · Fee on file at submit
                </span>
              )}
            </p>
          </ReviewSection>

          <Separator className="bg-slate-800" />

          <ReviewSection title="Business name" step="name">
            <p className="whitespace-pre-wrap font-medium text-white">
              {businessDisplay || "—"}
            </p>
          </ReviewSection>

          <Separator className="bg-slate-800" />

          <ReviewSection title="Business purpose" step="details">
            <p className="whitespace-pre-wrap">
              {data.businessPurpose?.trim() || "—"}
            </p>
          </ReviewSection>

          <ReviewSection title="Management" step="details">
            <p>{managementLabel(data.managementType)}</p>
          </ReviewSection>

          <Separator className="bg-slate-800" />

          <ReviewSection title="Registered agent" step="agent">
            <p className="font-medium text-white">{agentSummary.headline}</p>
            {agent?.isCommercial && (
              <p className="text-xs text-slate-500">Commercial registered office</p>
            )}
            <pre className="mt-2 whitespace-pre-wrap font-sans text-slate-300">
              {agentSummary.addressBlock}
            </pre>
          </ReviewSection>

          <Separator className="bg-slate-800" />

          <ReviewSection title="Principal address" step="address">
            <pre className="whitespace-pre-wrap font-sans text-slate-300">
              {formatAddress(data.principalAddress)}
            </pre>
          </ReviewSection>

          {mailingDifferent ? (
            <>
              <Separator className="bg-slate-800" />
              <ReviewSection title="Mailing address" step="address">
                <pre className="whitespace-pre-wrap font-sans text-slate-300">
                  {formatAddress(data.mailingAddress)}
                </pre>
              </ReviewSection>
            </>
          ) : null}

          <Separator className="bg-slate-800" />

          <ReviewSection title="Members" step="members">
            {data.members && data.members.length > 0 ? (
              <ul className="space-y-4">
                {data.members.map((m: Member) => (
                  <li
                    key={m.id}
                    className="rounded-lg border border-slate-800 bg-slate-950/50 p-3"
                  >
                    <p className="font-medium text-white">{m.name || "—"}</p>
                    <p className="text-xs text-slate-500">
                      {memberRoleLabel(m.role)}
                      {m.ownershipPercentage != null &&
                        m.ownershipPercentage > 0 &&
                        ` · ${m.ownershipPercentage}% ownership`}
                      {m.isOrganizer ? " · Organizer" : ""}
                    </p>
                    <pre className="mt-2 whitespace-pre-wrap font-sans text-xs text-slate-400">
                      {formatAddress(m.address)}
                    </pre>
                  </li>
                ))}
              </ul>
            ) : (
              <p>—</p>
            )}
          </ReviewSection>
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50 text-white">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg text-white">Submit</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-400">
            By clicking Submit, you agree to our{" "}
            <Link
              href="/terms"
              className="text-cyan-400 underline-offset-4 hover:text-cyan-300 hover:underline"
            >
              Terms of Service
            </Link>
            .
          </p>
          {submissionError ? (
            <p className="text-sm text-red-400" role="alert">
              {submissionError}
            </p>
          ) : null}
          <Button
            type="button"
            disabled={isSubmitting}
            onClick={handleSubmit}
            className="w-full bg-gradient-to-r from-teal-400 to-cyan-500 text-slate-950 hover:from-teal-300 hover:to-cyan-400 sm:w-auto"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Submitting…
              </>
            ) : (
              "Submit formation"
            )}
          </Button>
        </CardContent>
      </Card>

      <div className="mt-8 flex items-center justify-between">
        <Button
          type="button"
          variant="ghost"
          onClick={prevStep}
          className="text-slate-400 hover:text-white"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <div />
      </div>
    </div>
  );
}
