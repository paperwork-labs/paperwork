import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import type { ConversationsListPage } from "@/types/conversations";
import { ConversationsClient } from "./conversations-client";

export const dynamic = "force-dynamic";

async function fetchInitialPage(
  root: string,
  secret: string,
): Promise<ConversationsListPage | null> {
  try {
    const res = await fetch(
      `${root}/admin/conversations?filter=needs-action&limit=50`,
      {
        headers: { "X-Brain-Secret": secret },
        cache: "no-store",
      },
    );
    if (!res.ok) return null;
    const json = await res.json();
    if (!json.success || !json.data) return null;
    return json.data as ConversationsListPage;
  } catch {
    return null;
  }
}

export default async function ConversationsPage() {
  const auth = getBrainAdminFetchOptions();
  const brainConfigured = auth.ok;

  let initialPage: ConversationsListPage | null = null;
  if (auth.ok) {
    initialPage = await fetchInitialPage(auth.root, auth.secret);
  }

  return (
    <ConversationsClient
      brainConfigured={brainConfigured}
      initialPage={initialPage}
    />
  );
}
