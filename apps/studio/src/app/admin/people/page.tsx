import { Suspense, type ReactNode } from "react";

import { Skeleton } from "@paperwork-labs/ui";

import { BrainClient, BrainClientError } from "@/lib/brain-client";
import { loadPersonasPageData } from "@/lib/personas";

import { PersonasTabsClient } from "../brain/personas/personas-tabs-client";

import {
  EmployeeOrgGrid,
  PeopleDirectoryBrainError,
} from "./employee-org-grid";
import { PeopleAdminShell } from "./people-admin-shell";

export const dynamic = "force-dynamic";

type PageProps = { searchParams: Promise<{ view?: string }> };

function PersonasWorkspaceFallback() {
  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-8 md:px-6">
      <Skeleton className="mb-4 h-10 w-72 max-w-full" />
      <Skeleton className="h-12 w-full max-w-lg rounded-lg" />
      <Skeleton className="mt-6 h-[320px] w-full rounded-xl" />
    </div>
  );
}

async function renderDirectory(): Promise<ReactNode> {
  const client = BrainClient.fromEnv();
  if (!client) {
    return (
      <PeopleDirectoryBrainError message="Brain admin API not configured (BRAIN_API_URL / BRAIN_API_SECRET)." />
    );
  }
  try {
    const employees = await client.getEmployees();
    return <EmployeeOrgGrid employees={employees} />;
  } catch (err) {
    const message =
      err instanceof BrainClientError
        ? err.message
        : err instanceof Error
          ? err.message
          : "Unknown error talking to Brain";
    return <PeopleDirectoryBrainError message={message} />;
  }
}

export default async function AdminPeoplePage({ searchParams }: PageProps) {
  const { view } = await searchParams;
  const [directory, data] = await Promise.all([renderDirectory(), loadPersonasPageData()]);

  return (
    <PeopleAdminShell
      view={view}
      directory={directory}
      workspace={
        <Suspense fallback={<PersonasWorkspaceFallback />}>
          <PersonasTabsClient data={data} />
        </Suspense>
      }
    />
  );
}
