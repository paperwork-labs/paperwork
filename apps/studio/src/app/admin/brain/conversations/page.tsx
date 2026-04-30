import { resolveComposePersonaOptions } from "@/lib/compose-persona-options";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import {
  countFounderActionItems,
  readFounderActionsJsonFromDisk,
} from "@/lib/founder-actions-source";
import { getE2EMutableListPage } from "@/lib/e2e-conversations-mutable";
import { getE2EConversationsListPage } from "@/lib/e2e-conversations-fixture";
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
        composePersonaOptions={composePersonaOptions}
        replyPersonas={replyPersonas}
      />
    );
  }

  if (!auth.ok) {
    return (
      <ConversationsClient
        brainConfigured={false}
        initialPage={null}
        setupError={null}
        composePersonaOptions={composePersonaOptions}
        replyPersonas={replyPersonas}
      />
    );
  }

  const disk = readFounderActionsJsonFromDisk();
  if (!disk.ok) {
    return (
      <ConversationsClient
        brainConfigured
        initialPage={null}
        setupError={disk.message}
        composePersonaOptions={composePersonaOptions}
        replyPersonas={replyPersonas}
      />
    );
  }

  let setupError: string | null = null;
  const backfill = await postBackfill(auth.root, auth.secret);
  if (!backfill.ok) {
    setupError = backfill.error ?? "Backfill request failed.";
  } else if (backfill.data?.parse_error) {
    setupError = backfill.data.parse_error;
  } else if (
    backfill.data?.source_kind === "none" &&
    countFounderActionItems(disk.parsed) > 0
  ) {
    setupError =
      "Founder actions exist in apps/studio/src/data/founder-actions.json, but Brain could not load any founder-actions source. Check Brain deployment has monorepo files and REPO_ROOT.";
  }

  let initialPage: ConversationsListPage | null = null;
  if (!setupError) {
    const listed = await fetchListPage(auth.root, auth.secret);
    if (listed.error) {
      setupError = listed.error;
    } else {
      initialPage = listed.page;
    }
  }

  return (
    <ConversationsClient
      brainConfigured
      initialPage={initialPage}
      setupError={setupError}
      composePersonaOptions={composePersonaOptions}
      replyPersonas={replyPersonas}
    />
  );
}
