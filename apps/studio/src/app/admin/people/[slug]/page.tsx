import Link from "next/link";
import { notFound } from "next/navigation";

import { ArrowLeft } from "lucide-react";

import { HqMissingCredCard } from "@/components/admin/hq/HqMissingCredCard";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { BrainClient, BrainClientError, type EmployeeActivityPayload } from "@/lib/brain-client";

import { EmployeeProfileTabsClient } from "./employee-profile-tabs-client";

export const dynamic = "force-dynamic";

type PageProps = { params: Promise<{ slug: string }> };

function emptyEmployeeActivity(): EmployeeActivityPayload {
  return {
    dispatches: [],
    conversations: [],
    transcript_episodes: [],
  };
}

export default async function EmployeeProfilePage({ params }: PageProps) {
  const { slug } = await params;

  const client = BrainClient.fromEnv();
  if (!client) {
    return (
      <div className="space-y-8">
        <HqPageHeader
          breadcrumbs={[
            { label: "Admin", href: "/admin" },
            { label: "People", href: "/admin/people" },
            { label: slug },
          ]}
          title="Employee profile"
          subtitle="Load a teammate from Brain to see org context, persona config, and ownership."
        />
        <HqMissingCredCard
          service="Brain admin API"
          envVar="BRAIN_API_SECRET"
          description="Set BRAIN_API_URL and BRAIN_API_SECRET in Vercel / Render, redeploy, then reload this profile. Employee detail uses GET /admin/employees/{slug}."
          reconnectAction={{
            label: "Open environment docs",
            href: "https://vercel.com/docs/projects/environment-variables",
          }}
        />
      </div>
    );
  }

  let employee;
  try {
    employee = await client.getEmployee(slug);
  } catch (err) {
    if (err instanceof BrainClientError && err.status === 404) {
      notFound();
    }
    const message =
      err instanceof BrainClientError
        ? err.message
        : err instanceof Error
          ? err.message
          : "Unknown error talking to Brain";
    return (
      <div className="space-y-8">
        <HqPageHeader
          breadcrumbs={[
            { label: "Admin", href: "/admin" },
            { label: "People", href: "/admin/people" },
            { label: slug },
          ]}
          title="Employee profile"
          subtitle={`Could not load “${slug}”.`}
          actions={
            <Link
              href="/admin/people"
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/80 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-800"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden />
              Back to People
            </Link>
          }
        />
        <div
          className="rounded-lg border border-red-700/45 bg-red-950/25 px-4 py-3 text-sm text-red-100"
          role="alert"
        >
          <p className="font-semibold text-red-200">Brain unavailable or error</p>
          <p className="mt-1 text-red-100/90">{message}</p>
          <p className="mt-3 text-xs text-red-300/85">
            Check BRAIN_API_URL / BRAIN_API_SECRET and Brain health; then reconnect and refresh.
            Listing still works when only this slug fails — try returning to People and opening another card.
          </p>
        </div>
      </div>
    );
  }

  let activity: EmployeeActivityPayload = emptyEmployeeActivity();
  try {
    activity = await client.getEmployeeActivity(slug);
  } catch {
    activity = emptyEmployeeActivity();
  }

  const trimmedDisplay = employee.display_name?.trim() ?? "";
  const trimmedTagline = employee.tagline?.trim() ?? "";
  const primaryHeadline =
    trimmedDisplay ||
    employee.role_title?.trim() ||
    employee.slug;
  const emojiDisplay = employee.avatar_emoji?.trim() || "◇";

  const mutedContextSubtitle =
    !trimmedTagline && trimmedDisplay
      ? `${employee.team}`.trim()
      : !trimmedTagline && !trimmedDisplay
        ? `${employee.role_title} · ${employee.team}`
        : undefined;

  const titleContent = (
    <div className="flex flex-wrap items-start gap-3 md:gap-4">
      <span
        className="select-none text-4xl leading-none md:text-[2.75rem]"
        aria-hidden
      >
        {emojiDisplay}
      </span>
      <div className="min-w-0 space-y-1">
        <span className="block text-lg font-semibold tracking-tight text-zinc-100 md:text-xl lg:text-2xl">
          {primaryHeadline}
        </span>
        {trimmedDisplay ? (
          <span className="block text-sm text-zinc-400">{employee.role_title}</span>
        ) : null}
        {trimmedTagline ? (
          <span className="block text-sm text-zinc-400">{trimmedTagline}</span>
        ) : null}
      </div>
    </div>
  );

  return (
    <div className="space-y-8">
      <HqPageHeader
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "People", href: "/admin/people" },
          { label: primaryHeadline },
        ]}
        title={titleContent}
        subtitle={mutedContextSubtitle}
        actions={
          <Link
            href="/admin/people"
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/80 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-800"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
            Directory
          </Link>
        }
      />

      <EmployeeProfileTabsClient employee={employee} activity={activity} />
    </div>
  );
}
