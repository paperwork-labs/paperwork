import { Suspense } from "react";

import { Skeleton } from "@paperwork-labs/ui";

import {
  loadPersonaBrainYamlMap,
  personaAutonomyLabel,
  personaDomainLabel,
} from "@/lib/persona-brain-yaml";
import { loadPersonasPageData } from "@/lib/personas";
import type { ActivityFeedRow } from "@/lib/personas-types";

import { PersonasTabsClient } from "../brain/personas/personas-tabs-client";

import { PeopleAdminShell } from "./people-admin-shell";
import { PeopleEmployeesClient, type PeopleEmployeeRow } from "./people-employees-client";

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

function activityMatchesPersona(row: ActivityFeedRow, personaId: string): boolean {
  const p = row.persona.toLowerCase();
  const id = personaId.toLowerCase();
  if (p === id) return true;
  if (p.includes(id)) return true;
  const stripped = p.replace(/^model:/, "");
  if (stripped.includes(id)) return true;
  return false;
}

function buildEmployeeRows(
  registry: Awaited<ReturnType<typeof loadPersonasPageData>>["registry"],
  activityRows: ActivityFeedRow[],
  yamlMap: ReturnType<typeof loadPersonaBrainYamlMap>,
): PeopleEmployeeRow[] {
  return registry.map((r) => {
    const y = yamlMap.get(r.personaId.toLowerCase());
    const recent = activityRows
      .filter((row) => activityMatchesPersona(row, r.personaId))
      .slice(0, 3);
    return {
      personaId: r.personaId,
      displayName: r.name,
      description: r.description,
      domainLabel: personaDomainLabel(r.personaId, y),
      autonomyLabel: personaAutonomyLabel(y),
      routingActive: r.routingActive,
      recentActivity: recent,
    };
  });
}

export default async function AdminPeoplePage({ searchParams }: PageProps) {
  const { view } = await searchParams;
  const data = await loadPersonasPageData();
  const yamlMap = loadPersonaBrainYamlMap();
  const employees = buildEmployeeRows(data.registry, data.activity.rows, yamlMap);

  return (
    <PeopleAdminShell
      view={view}
      directory={
        <PeopleEmployeesClient employees={employees} brainApiError={data.brainApiError ?? null} />
      }
      workspace={
        <Suspense fallback={<PersonasWorkspaceFallback />}>
          <PersonasTabsClient data={data} />
        </Suspense>
      }
    />
  );
}
