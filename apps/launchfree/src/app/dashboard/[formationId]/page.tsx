import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  Download,
  FileCheck2,
  MapPin,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@paperwork-labs/ui";
import type { FormationDashboardStatus } from "@/lib/dashboard-formations";
import {
  getFormationById,
  getNextStepsGuidance,
} from "@/lib/dashboard-formations";
import { StatusTimeline } from "../components/status-timeline";

const statusBadgeClass: Record<FormationDashboardStatus, string> = {
  draft:
    "border-slate-600 bg-slate-800/80 text-slate-300 hover:bg-slate-800/80",
  pending:
    "border-amber-500/40 bg-amber-500/10 text-amber-200 hover:bg-amber-500/10",
  submitted:
    "border-sky-500/40 bg-sky-500/10 text-sky-200 hover:bg-sky-500/10",
  confirmed:
    "border-emerald-500/40 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/10",
  failed:
    "border-red-500/40 bg-red-500/10 text-red-200 hover:bg-red-500/10",
};

const statusLabel: Record<FormationDashboardStatus, string> = {
  draft: "Draft",
  pending: "Pending",
  submitted: "Submitted",
  confirmed: "Confirmed",
  failed: "Failed",
};

interface PageProps {
  params: Promise<{ formationId: string }>;
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { formationId } = await params;
  const formation = await getFormationById(formationId);
  if (!formation) {
    return { title: "Formation not found — LaunchFree" };
  }
  return {
    title: `${formation.llcName} — LaunchFree`,
    description: `Formation status for ${formation.llcName} in ${formation.stateCode}.`,
  };
}

export default async function FormationDetailPage({ params }: PageProps) {
  const { formationId } = await params;
  const formation = await getFormationById(formationId);
  if (!formation) {
    notFound();
  }

  const guidance = getNextStepsGuidance(formation.status);
  const pdfReady = Boolean(formation.articlesPdfUrl);
  const canRetryWizard = formation.status === "draft" || formation.status === "failed";

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <Button
          variant="ghost"
          asChild
          className="-ml-2 mb-4 gap-2 text-slate-400 hover:bg-slate-800/60 hover:text-teal-300"
        >
          <Link href="/dashboard">
            <ArrowLeft className="size-4" aria-hidden />
            Back to dashboard
          </Link>
        </Button>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-slate-50 sm:text-3xl">
                {formation.llcName}
              </h1>
              <Badge
                variant="outline"
                className={statusBadgeClass[formation.status]}
              >
                {statusLabel[formation.status]}
              </Badge>
            </div>
            <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-400">
              <span className="inline-flex items-center gap-1.5">
                <MapPin className="size-3.5 text-teal-400/90" aria-hidden />
                {formation.stateCode}
                {formation.principalCity
                  ? ` · ${formation.principalCity}`
                  : null}
              </span>
            </p>
          </div>

          <div className="flex shrink-0 flex-col gap-2 sm:items-end">
            {pdfReady && formation.articlesPdfUrl ? (
              <Button
                asChild
                variant="outline"
                className="w-full border-slate-700 bg-slate-900/50 text-slate-100 hover:bg-slate-800 hover:text-teal-200 sm:w-auto"
              >
                <a
                  href={formation.articlesPdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="gap-2"
                >
                  <Download className="size-4" aria-hidden />
                  Download PDF
                </a>
              </Button>
            ) : (
              <Button
                type="button"
                variant="outline"
                disabled
                title="Articles PDF will be available once your documents are generated."
                className="w-full cursor-not-allowed border-slate-700 bg-slate-900/30 text-slate-500 sm:w-auto"
              >
                <Download className="size-4 opacity-50" aria-hidden />
                Download PDF
              </Button>
            )}
            {canRetryWizard ? (
              <Button
                asChild
                variant="secondary"
                className="w-full border border-slate-700 bg-slate-800/50 text-slate-200 hover:bg-slate-800 sm:w-auto"
              >
                <Link href="/form">Continue in wizard</Link>
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-6">
        {formation.filingConfirmationNumber ? (
          <Card className="border-slate-800 bg-slate-900/50">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base text-slate-100">
                <FileCheck2 className="size-4 text-teal-400" aria-hidden />
                Filing confirmation
              </CardTitle>
              <CardDescription className="text-slate-500">
                Save this number for your records and banking applications.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="font-mono text-lg font-medium tracking-wide text-teal-200">
                {formation.filingConfirmationNumber}
              </p>
            </CardContent>
          </Card>
        ) : null}

        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-lg text-slate-100">Next steps</CardTitle>
            <CardDescription className="text-slate-500">
              {guidance.title}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-slate-400">
              {guidance.body}
            </p>
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg text-slate-100">
              <Building2 className="size-4 text-teal-400" aria-hidden />
              Formation details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between gap-4 border-b border-slate-800/80 py-2">
              <span className="text-slate-500">Legal name</span>
              <span className="text-right font-medium text-slate-200">
                {formation.llcName}
              </span>
            </div>
            <div className="flex justify-between gap-4 border-b border-slate-800/80 py-2">
              <span className="text-slate-500">State</span>
              <span className="text-right font-medium text-slate-200">
                {formation.stateCode}
              </span>
            </div>
            {formation.businessPurpose ? (
              <div className="flex justify-between gap-4 border-b border-slate-800/80 py-2">
                <span className="text-slate-500">Purpose</span>
                <span className="max-w-[60%] text-right text-slate-200">
                  {formation.businessPurpose}
                </span>
              </div>
            ) : null}
            {formation.managementType ? (
              <div className="flex justify-between gap-4 py-2">
                <span className="text-slate-500">Management</span>
                <span className="text-right capitalize text-slate-200">
                  {formation.managementType}-managed
                </span>
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-lg text-slate-100">Status history</CardTitle>
            <CardDescription className="text-slate-500">
              What happened and when — updates appear as your filing progresses.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <StatusTimeline events={formation.statusHistory} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
