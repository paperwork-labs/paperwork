import {
  loadPersonaBrainYamlMap,
  personaAutonomyLabel,
  personaDomainLabel,
} from "@/lib/persona-brain-yaml";
import { loadPersonasPageData } from "@/lib/personas";
import type { ActivityFeedRow } from "@/lib/personas-types";

import { PeopleEmployeesClient, type PeopleEmployeeRow } from "./people-employees-client";

export const dynamic = "force-dynamic";

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

export default async function AdminPeoplePage() {
  const data = await loadPersonasPageData();
  const yamlMap = loadPersonaBrainYamlMap();
  const employees = buildEmployeeRows(data.registry, data.activity.rows, yamlMap);
  return (
    <PeopleEmployeesClient employees={employees} brainApiError={data.brainApiError ?? null} />
  );
}
