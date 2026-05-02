import { BrainClient, type EmployeeListItem } from "@/lib/brain-client";
import { resolveComposePersonaOptions } from "@/lib/compose-persona-options";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import {
  countFounderActionItems,
  readFounderActionsJsonFromDisk,
} from "@/lib/founder-actions-source";
import { getE2EMutableListPage } from "@/lib/e2e-conversations-mutable";
import { getRepoRoot, loadPersonaRegistry } from "@/lib/personas";
import type { ConversationsListPage } from "@/types/conversations";
import type { BrainPersonaOption } from "./conversation-composer";
import { ConversationsClient } from "./conversations-client";

export const dynamic = "force-dynamic";

function loadReplyPersonas(): BrainPersonaOption[] {
  try {
    const root = getRepoRoot();
    return loadPersonaRegistry(root).map((r) => ({
      id: r.personaId,
      label: r.name,
      description: r.description,
    }));
  } catch {
    return [];
  }
}

type BackfillPayload = {
  created?: number;
  source_kind?: string;
  parse_error?: string | null;
};

async function postBackfill(
  root: string,
  secret: string,
): Promise<{ ok: boolean; data?: BackfillPayload; error?: string }> {
  try {
    const res = await fetch(`${root}/admin/conversations/_backfill-founder-actions`, {
      method: "POST",
      headers: { "X-Brain-Secret": secret },
      cache: "no-store",
    });
    const json = (await res.json()) as {
      success?: boolean;
      data?: BackfillPayload;
      error?: string;
    };
    if (!res.ok || !json.success) {
      return { ok: false, error: json.error ?? `Backfill failed (${res.status})` };
    }
    return { ok: true, data: json.data };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Network error during backfill" };
  }
}

async function fetchListPage(
  root: string,
  secret: string,
): Promise<{ page: ConversationsListPage | null; error: string | null }> {
  try {
    const res = await fetch(`${root}/admin/conversations?filter=needs-action&limit=50`, {
      headers: { "X-Brain-Secret": secret },
      cache: "no-store",
    });
    if (!res.ok) {
      return { page: null, error: `Failed to load conversations (${res.status})` };
    }
    const json = (await res.json()) as {
      success?: boolean;
      data?: ConversationsListPage;
      error?: string;
    };
    if (!json.success || !json.data) {
      return { page: null, error: json.error ?? "Brain returned no conversation data." };
    }
    return { page: json.data, error: null };
  } catch (e) {
    return {
      page: null,
      error: e instanceof Error ? e.message : "Network error loading conversations",
    };
  }
}

async function loadPersonaContextEnrichment(): Promise<{
  employeeRoster: EmployeeListItem[];
  personaDispatchBySlug: Record<string, number>;
}> {
  const client = BrainClient.fromEnv();
  if (!client) return { employeeRoster: [], personaDispatchBySlug: {} };
  let employeeRoster: EmployeeListItem[] = [];
  let personaDispatchBySlug: Record<string, number> = {};
  try {
    employeeRoster = await client.getEmployees();
  } catch {
    /* roster optional — inbox still works */
  }
  try {
    const summary = await client.getPersonaDispatchSummary();
    for (const row of summary.personas) {
      personaDispatchBySlug[row.persona_slug] = row.recent_dispatch_count_30d;
    }
  } catch {
    /* dispatch summary optional */
  }
  return { employeeRoster, personaDispatchBySlug };
}

export default async function ConversationsPage() {
  const composePersonaOptions = await resolveComposePersonaOptions();
  const auth = getBrainAdminFetchOptions();
  const replyPersonas = loadReplyPersonas();

  if (process.env.STUDIO_E2E_FIXTURE === "1") {
    return (
      <ConversationsClient
        brainConfigured
        initialPage={getE2EMutableListPage()}
        setupError={null}
        setupWarning={null}
        composePersonaOptions={composePersonaOptions}
        replyPersonas={replyPersonas}
        employeeRoster={[]}
        personaDispatchBySlug={{}}
      />
    );
  }

  if (!auth.ok) {
    return (
      <ConversationsClient
        brainConfigured={false}
        initialPage={null}
        setupError={null}
        setupWarning={null}
        composePersonaOptions={composePersonaOptions}
        replyPersonas={replyPersonas}
        employeeRoster={[]}
        personaDispatchBySlug={{}}
      />
    );
  }

  let setupWarning: string | null = null;
  try {
    const disk = readFounderActionsJsonFromDisk();
    if (!disk.ok) {
      console.warn("[conversations] founder-actions disk:", disk.message);
      setupWarning = disk.message;
    } else {
      const backfill = await postBackfill(auth.root, auth.secret);
      if (!backfill.ok) {
        console.warn("[conversations] backfill:", backfill.error);
        setupWarning = backfill.error ?? "Backfill request failed (inbox still loads).";
      } else if (backfill.data?.parse_error) {
        console.warn("[conversations] backfill parse_error:", backfill.data.parse_error);
        setupWarning = backfill.data.parse_error;
      } else if (
        backfill.data?.source_kind === "none" &&
        countFounderActionItems(disk.parsed) > 0
      ) {
        const msg =
          "Founder actions exist in apps/studio/src/data/founder-actions.json, but Brain could not load any founder-actions source. Check Brain deployment has monorepo files and REPO_ROOT.";
        console.warn("[conversations]", msg);
        setupWarning = msg;
      }
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.warn("[conversations] disk/backfill setup:", msg);
    setupWarning = `Setup step skipped: ${msg}`;
  }

  const listed = await fetchListPage(auth.root, auth.secret);
  const setupError =
    listed.error && !listed.page ? listed.error : null;
  const initialPage = listed.page;
  const { employeeRoster, personaDispatchBySlug } = await loadPersonaContextEnrichment();

  return (
    <ConversationsClient
      brainConfigured
      initialPage={initialPage}
      setupError={setupError}
      setupWarning={setupWarning}
      composePersonaOptions={composePersonaOptions}
      replyPersonas={replyPersonas}
      employeeRoster={employeeRoster}
      personaDispatchBySlug={personaDispatchBySlug}
    />
  );
}
