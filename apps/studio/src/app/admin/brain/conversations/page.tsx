import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import {
  countFounderActionItems,
  readFounderActionsJsonFromDisk,
} from "@/lib/founder-actions-source";
import { getE2EConversationsListPage } from "@/lib/e2e-conversations-fixture";
import type { ConversationsListPage } from "@/types/conversations";
import { ConversationsClient } from "./conversations-client";

export const dynamic = "force-dynamic";

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
  const auth = getBrainAdminFetchOptions();

  if (process.env.STUDIO_E2E_FIXTURE === "1") {
    return (
      <ConversationsClient
        brainConfigured
        initialPage={getE2EConversationsListPage()}
        setupError={null}
      />
    );
  }

  if (!auth.ok) {
    return <ConversationsClient brainConfigured={false} initialPage={null} setupError={null} />;
  }

  const disk = readFounderActionsJsonFromDisk();
  if (!disk.ok) {
    return (
      <ConversationsClient brainConfigured initialPage={null} setupError={disk.message} />
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
    <ConversationsClient brainConfigured initialPage={initialPage} setupError={setupError} />
  );
}
