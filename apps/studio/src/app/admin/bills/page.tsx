import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import { BillsClient } from "./bills-client";
import type { BillsListPage } from "@/types/bills";

export const dynamic = "force-dynamic";

async function fetchBills(auth: { root: string; secret: string }): Promise<BillsListPage | null> {
  try {
    const res = await fetch(`${auth.root}/admin/bills`, {
      headers: { "X-Brain-Secret": auth.secret },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const json = await res.json();
    if (!json.success) return null;
    return json.data as BillsListPage;
  } catch {
    return null;
  }
}

export default async function BillsPage() {
  const auth = getBrainAdminFetchOptions();

  if (!auth.ok) {
    return (
      <div className="rounded-xl border border-red-900/40 bg-red-500/5 p-8 text-center">
        <p className="text-sm font-medium text-red-400">Brain API not configured</p>
        <p className="mt-1 text-xs text-red-500/70">
          Set BRAIN_API_URL and BRAIN_API_SECRET to enable Bills.
        </p>
      </div>
    );
  }

  const page = await fetchBills(auth);
  return <BillsClient initialPage={page} />;
}
